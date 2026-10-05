# tests/shared/workers/test_base__stale_code_gate.py
"""ADR-030 / ADR-169 D3: an acting worker does not act on stale code.

The gate lives in the Worker base, so it covers both entry points: one-shot
``start()`` and the ScheduledWorker ``run_loop()``. Sensing workers keep
running; a suspended cycle is recorded (heartbeat + report), never silent.
"""

from __future__ import annotations

import asyncio
import copy
import uuid
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.code_identity import CodeDrift
from shared.workers.base import Worker
from shared.workers.scheduled_worker import ScheduledWorker


_DECLARATION: dict[str, Any] = {
    "kind": "worker",
    "metadata": {
        "id": "workers.gate_stub",
        "title": "Gate Stub",
        "version": "1.0.0",
        "authority": "policy",
        "status": "active",
    },
    "identity": {"uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "class": "acting"},
    "mandate": {
        "responsibility": "Gate stub.",
        "phase": "execution",
        "permitted_tools": [],
        "scope": {},
        "approval_required": False,
        "schedule": {"max_interval": 300},
    },
    "implementation": {},
}

_STALE = CodeDrift(state="stale", loaded_identity="a" * 64, disk_identity="b" * 64)
_MATCH = CodeDrift(state="match", loaded_identity="a" * 64, disk_identity="a" * 64)
_UNKNOWN = CodeDrift(state="unknown", reason="git failed")


def _build(base: type, worker_class: str) -> Any:
    declaration = copy.deepcopy(_DECLARATION)
    declaration["identity"]["class"] = worker_class
    ran: list[bool] = []

    class _Stub(base):  # type: ignore[misc, valid-type]
        declaration_name: ClassVar[str] = "gate_stub"

        async def run(self) -> None:
            ran.append(True)
            await self.post_heartbeat()

    repo = MagicMock()
    repo.load_worker.return_value = declaration
    with (
        patch("shared.workers.base.get_intent_repository", return_value=repo),
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _Stub()
    bb = MagicMock()
    bb.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    bb.post_report = AsyncMock(return_value=uuid.uuid4())
    bb._post_entry = AsyncMock(return_value=uuid.uuid4())
    worker._blackboard = bb
    worker._register = AsyncMock()
    worker._release_held_claims = AsyncMock(return_value=0)
    worker._renew_lease_until_cancelled = AsyncMock()
    return worker, ran


@pytest.mark.parametrize("drift", [_STALE, _UNKNOWN])
async def test_acting_worker_skips_its_cycle_and_says_so(drift: CodeDrift) -> None:
    worker, ran = _build(Worker, "acting")
    with patch("shared.workers.base.code_drift", return_value=drift):
        await worker.start()

    assert ran == []
    worker._blackboard.post_heartbeat.assert_awaited()
    subject, payload = worker._blackboard.post_report.await_args.args
    assert subject == "gate_stub.suspended.stale_code"
    assert payload["rule"] == "governance.stale_daemon"
    assert payload["state"] == drift.state


async def test_acting_worker_runs_on_the_code_on_disk() -> None:
    worker, ran = _build(Worker, "acting")
    with patch("shared.workers.base.code_drift", return_value=_MATCH):
        await worker.start()
    assert ran == [True]


async def test_sensing_worker_keeps_running_on_stale_code() -> None:
    worker, ran = _build(Worker, "sensing")
    with patch("shared.workers.base.code_drift", return_value=_STALE):
        await worker.start()
    assert ran == [True]
    worker._blackboard.post_report.assert_not_awaited()


async def test_scheduled_acting_worker_is_gated_too() -> None:
    worker, ran = _build(ScheduledWorker, "acting")
    with (
        patch("shared.workers.base.code_drift", return_value=_STALE),
        patch(
            "shared.workers.scheduled_worker.asyncio.sleep",
            AsyncMock(side_effect=asyncio.CancelledError),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await worker.run_loop()

    assert ran == []
    # Suspension posts, so the silence invariant does not fire.
    worker._blackboard._post_entry.assert_not_awaited()
    assert (
        worker._blackboard.post_report.await_args.args[0]
        == "gate_stub.suspended.stale_code"
    )
