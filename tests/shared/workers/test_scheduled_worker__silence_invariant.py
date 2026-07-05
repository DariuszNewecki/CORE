# tests/shared/workers/test_scheduled_worker__silence_invariant.py
"""Unit tests for ScheduledWorker per-cycle silence invariant.

The constitution requires every run() cycle to post at least one blackboard
entry. Worker.start() enforces this for Model A workers. ScheduledWorker
run_loop() must enforce the same invariant for Model B workers.

Two cases:
- Silent run (no post) → WorkerSilenceError raised inside the try block,
  caught by the loop's except block, and recorded via _blackboard._post_entry.
- Posting run (heartbeat) → no silence error; _post_entry not called for
  silence.

The loop is exited after one cycle by having asyncio.sleep raise
CancelledError — which escapes except Exception (BaseException in 3.8+).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.workers.scheduled_worker import ScheduledWorker


_VALID_DECLARATION: dict[str, Any] = {
    "kind": "worker",
    "metadata": {
        "id": "workers.scheduled_stub",
        "title": "Scheduled Stub",
        "version": "1.0.0",
        "authority": "policy",
        "status": "active",
    },
    "identity": {"uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "class": "sensing"},
    "mandate": {
        "responsibility": "Silence invariant stub.",
        "phase": "audit",
        "permitted_tools": [],
        "scope": {},
        "approval_required": False,
        "schedule": {"max_interval": 300},
    },
    "implementation": {},
}


def _make_scheduled_worker(run_impl) -> ScheduledWorker:
    """Build a ScheduledWorker with a given run() and no DB calls."""

    class _ScheduledStub(ScheduledWorker):
        declaration_name: ClassVar[str] = "scheduled_stub"

        async def run(self) -> None:
            await run_impl(self)

    mock_repo = MagicMock()
    mock_repo.load_worker.return_value = _VALID_DECLARATION

    with (
        patch("shared.workers.base.get_intent_repository", return_value=mock_repo),
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _ScheduledStub()

    mock_bb = MagicMock()
    mock_bb.post_finding = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_report = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    mock_bb._post_entry = AsyncMock(return_value=uuid.uuid4())
    worker._blackboard = mock_bb

    return worker


async def _silent(_worker: ScheduledWorker) -> None:
    """run() that never posts anything."""


async def _heartbeat(worker: ScheduledWorker) -> None:
    """run() that posts exactly one heartbeat."""
    await worker.post_heartbeat()


async def _one_cycle_sleep(*_args: Any) -> None:
    """Replaces asyncio.sleep; raises CancelledError to exit the loop after one cycle."""
    raise asyncio.CancelledError()


# ID: b3c9bd9f-3868-485f-9604-d520c07f0e65
@pytest.mark.asyncio
async def test_run_loop_reports_silence_when_run_posts_nothing() -> None:
    """run_loop() records WorkerSilenceError on the blackboard when run() is silent."""
    worker = _make_scheduled_worker(_silent)

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_before_loop", new_callable=AsyncMock),
        patch(
            "shared.workers.scheduled_worker.asyncio.sleep",
            side_effect=_one_cycle_sleep,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await worker.run_loop()

    worker._blackboard._post_entry.assert_called_once()
    call_kwargs = worker._blackboard._post_entry.call_args[1]
    assert "without posting" in call_kwargs.get("payload", {}).get("error", "")


# ID: 21583c17-73b8-4591-97e1-774387a4428a
@pytest.mark.asyncio
async def test_run_loop_no_silence_error_when_run_posts() -> None:
    """run_loop() does not record a silence error when run() posts a heartbeat."""
    worker = _make_scheduled_worker(_heartbeat)

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_before_loop", new_callable=AsyncMock),
        patch(
            "shared.workers.scheduled_worker.asyncio.sleep",
            side_effect=_one_cycle_sleep,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await worker.run_loop()

    worker._blackboard._post_entry.assert_not_called()


# ID: 350d184c-d566-4dc7-949e-be4cffd22ba3
@pytest.mark.asyncio
async def test_run_loop_resets_cycle_post_count_each_cycle() -> None:
    """_cycle_post_count is reset to 0 at the start of each cycle."""
    call_counts: list[int] = []

    async def _recording_run(worker: ScheduledWorker) -> None:
        call_counts.append(worker._cycle_post_count)
        await worker.post_heartbeat()

    worker = _make_scheduled_worker(_recording_run)

    # Run two cycles: first sleep passes, second raises CancelledError.
    sleep_call = 0

    async def _two_cycle_sleep(*_args: Any) -> None:
        nonlocal sleep_call
        sleep_call += 1
        if sleep_call >= 2:
            raise asyncio.CancelledError()

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_before_loop", new_callable=AsyncMock),
        patch(
            "shared.workers.scheduled_worker.asyncio.sleep",
            side_effect=_two_cycle_sleep,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await worker.run_loop()

    # _cycle_post_count must have been 0 at the start of both cycles.
    assert call_counts == [0, 0]
