# tests/shared/workers/test_base__blackboard_obligation.py
"""Unit tests for Worker blackboard-posting obligation (issue #724).

The constitution requires every Worker.run() cycle to produce at least one
blackboard entry. Worker.start() mechanically enforces this: if run() returns
normally without any post_* call, WorkerSilenceError is raised.

Three cases:
- Silent run (no post) → WorkerSilenceError
- Posting run (at least one post) → no error
- Failing run (run raises) → silence NOT checked; error-path is a distinct
  constitutional failure and is recorded via the worker.error blackboard entry
  posted by start()'s except block.
"""

from __future__ import annotations

import uuid
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.workers.base import Worker, WorkerSilenceError


# ── Shared stub declaration ────────────────────────────────────────────────────

_VALID_DECLARATION: dict = {
    "kind": "worker",
    "metadata": {
        "id": "workers.stub_worker",
        "title": "Obligation Stub",
        "version": "1.0.0",
        "authority": "policy",
        "status": "active",
    },
    "identity": {"uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "class": "sensing"},
    "mandate": {
        "responsibility": "Blackboard obligation stub.",
        "phase": "audit",
        "permitted_tools": [],
        "scope": {},
        "approval_required": False,
        "schedule": {"max_interval": 300},
    },
    "implementation": {},
}


def _make_worker(run_impl) -> Worker:
    """Build a concrete Worker with a given run() implementation, no DB calls."""

    class _ObligationStub(Worker):
        declaration_name: ClassVar[str] = "stub_worker"

        async def run(self) -> None:
            await run_impl(self)

    mock_repo = MagicMock()
    mock_repo.load_worker.return_value = _VALID_DECLARATION

    with (
        patch("shared.workers.base.get_intent_repository", return_value=mock_repo),
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _ObligationStub()

    # Replace the blackboard with a mock so post_* calls don't hit the DB.
    # The mock returns a fresh UUID for every call.
    mock_bb = MagicMock()
    mock_bb.post_finding = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_report = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_observation = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_artifact_finding = AsyncMock(return_value=uuid.uuid4())
    mock_bb._post_entry = AsyncMock(return_value=uuid.uuid4())
    worker._blackboard = mock_bb

    return worker


async def _silent(_worker: Worker) -> None:
    """run() that never posts anything."""


async def _heartbeat(worker: Worker) -> None:
    """run() that posts exactly one heartbeat."""
    await worker.post_heartbeat()


async def _raises(_worker: Worker) -> None:
    """run() that raises before posting anything."""
    raise RuntimeError("simulated worker failure")


# ── Tests ──────────────────────────────────────────────────────────────────────


# ID: 3de55354-3efd-4c33-93b6-f5eb810d2b46
@pytest.mark.asyncio
async def test_start_raises_silence_error_when_run_posts_nothing() -> None:
    """start() raises WorkerSilenceError when run() completes with zero posts."""
    worker = _make_worker(_silent)

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_renew_lease_until_cancelled", new_callable=AsyncMock),
        patch.object(worker, "_release_held_claims", new_callable=AsyncMock),
        pytest.raises(WorkerSilenceError, match="without posting"),
    ):
        await worker.start()


# ID: 5f584060-48ae-4ef5-ad14-4fbe42fc4054
@pytest.mark.asyncio
async def test_start_succeeds_when_run_posts_once() -> None:
    """start() completes normally when run() posts at least one heartbeat."""
    worker = _make_worker(_heartbeat)

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_renew_lease_until_cancelled", new_callable=AsyncMock),
        patch.object(worker, "_release_held_claims", new_callable=AsyncMock),
    ):
        await worker.start()  # must not raise

    assert worker._cycle_post_count == 1


# ID: ecbaad51-4dbc-4310-9ec9-9a2a6c276cb8
@pytest.mark.asyncio
async def test_start_does_not_check_silence_when_run_raises() -> None:
    """WorkerSilenceError is NOT raised when run() itself raises.

    A run() that fails before posting is an error-path failure, not a silence
    violation. start()'s except block records it as a worker.error blackboard
    entry — that entry is the constitutional record for this failed cycle.
    """
    worker = _make_worker(_raises)

    with (
        patch.object(worker, "_register", new_callable=AsyncMock),
        patch.object(worker, "_renew_lease_until_cancelled", new_callable=AsyncMock),
        patch.object(worker, "_release_held_claims", new_callable=AsyncMock),
        pytest.raises(RuntimeError, match="simulated worker failure"),
    ):
        await worker.start()

    # WorkerSilenceError must NOT be the raised exception — only the original error.
    # (pytest.raises above asserts exactly RuntimeError, so passing here proves it.)
