# tests/body/atomic/test_executor_audit_record_lost.py

"""F4: a lost audit record fails the run, not "success with a lost record".

When ``ActionAuditRecorder.record`` cannot persist the ``core.action_results``
row of a write action (every INSERT attempt raises), ``ActionExecutor.execute``
must return ``ok=False`` naming the lost record, while keeping the action's own
result details. Before F4 the gap was only logged (``AUDIT_GAP``) and the run
still returned ``ok=True``. Read actions keep the #634 boundary: a lost read
record is a warning and does not change the result.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.atomic.action_audit import ActionAuditRecorder
from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition, ActionRegistry
from shared.action_types import ActionResult


async def _succeed(**_kwargs) -> ActionResult:
    return ActionResult(
        action_id="test.audit_record_lost",
        ok=True,
        data={"path": "src/x.py", "changed": 1},
        duration_sec=0.0,
    )


def _executor() -> ActionExecutor:
    registry = ActionRegistry()
    registry.register(
        ActionDefinition(
            action_id="test.audit_record_lost",
            description="F4 lost-audit-record fixture",
            category=ActionCategory.FIX,
            policies=[],
            executor=_succeed,
            impact_level="safe",
        )
    )
    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.core_context.session_id = None
    # Every audit INSERT attempt fails: the record write raises.
    executor.core_context.registry.session = MagicMock(
        side_effect=RuntimeError("DB unavailable")
    )
    executor.registry = registry
    sandbox = MagicMock()
    sandbox.build_execution_context.return_value = (executor.core_context, None)
    executor._sandbox = sandbox
    return executor


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActionAuditRecorder, "_AUDIT_BACKOFF_BASE_SEC", 0.0)


async def test_write_run_fails_when_audit_record_write_raises() -> None:
    result = await _executor().execute(action_id="test.audit_record_lost", write=True)

    assert result.ok is False
    assert result.data["error_type"] == "AuditRecordLost"
    assert "AUDIT_GAP" in result.data["error"]
    assert "DB unavailable" in result.data["error"]
    # The action's own result details are kept, not hidden.
    assert result.data["action_ok"] is True
    assert result.data["path"] == "src/x.py"
    assert result.data["changed"] == 1


async def test_read_run_keeps_result_when_audit_record_write_raises() -> None:
    result = await _executor().execute(action_id="test.audit_record_lost", write=False)

    assert result.ok is True
    assert "error_type" not in result.data
