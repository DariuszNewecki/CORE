# tests/shared/workers/test_scheduled_worker__start_retry.py
"""run_loop survives a database that is down at daemon start (review M1).

_register() and _before_loop() reach the database; a failure there used to
end run_loop's task silently. They are now retried until both succeed.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

from shared.workers.scheduled_worker import ScheduledWorker


_DECLARATION: dict[str, Any] = {
    "kind": "worker",
    "metadata": {
        "id": "workers.retry_stub",
        "title": "Retry Stub",
        "version": "1.0.0",
        "authority": "policy",
        "status": "active",
    },
    "identity": {"uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeef", "class": "sensing"},
    "mandate": {
        "responsibility": "Retry stub.",
        "phase": "audit",
        "permitted_tools": [],
        "scope": {},
        "approval_required": False,
        "schedule": {"max_interval": 300},
    },
    "implementation": {},
}


class _StopLoop(BaseException):
    """Ends run_loop's endless cycle from inside the test."""


# ID: 3c8e1a57-6f24-4b9d-a0e3-7d5b2f9c4e18
async def test_register_failure_is_retried_then_the_loop_runs() -> None:
    ran: list[bool] = []

    class _Stub(ScheduledWorker):
        declaration_name: ClassVar[str] = "retry_stub"

        async def run(self) -> None:
            ran.append(True)
            await self.post_heartbeat()
            raise _StopLoop

    repo = MagicMock()
    repo.load_worker.return_value = copy.deepcopy(_DECLARATION)
    with (
        patch("shared.workers.base.get_intent_repository", return_value=repo),
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _Stub()
    bb = MagicMock()
    bb.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    worker._blackboard = bb
    worker._register = AsyncMock(
        side_effect=[ConnectionRefusedError("db down"), OSError("restarting"), None]
    )
    worker._suspended_for_stale_code = AsyncMock(return_value=False)
    sleep = AsyncMock()

    with patch("shared.workers.scheduled_worker.asyncio.sleep", sleep):
        try:
            await worker.run_loop()
        except _StopLoop:
            pass

    assert worker._register.await_count == 3
    assert [c.args[0] for c in sleep.await_args_list] == [5, 10]
    assert ran == [True]
