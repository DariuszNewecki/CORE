# tests/body/atomic/test_executor_audit_gap.py
"""#634: a write-action audit failure is surfaced loud, not swallowed.

`ActionExecutor._audit_log` is best-effort — it runs at step 7, after the
mutation has already landed (post-propagate), so it cannot roll the mutation
back. The #634 decision is that a ``write=True`` audit-persistence failure must
be LOUD (ERROR + an ``AUDIT_GAP`` marker) rather than a quiet warning, so the
one genuinely-silent case — a transient DB failure dropping the
``core.action_results`` row — becomes alertable. Read actions stay a quiet
best-effort warning.

These tests drive ``_audit_log`` with a session factory that raises (simulating
DB unavailability — the only real failure mode, since the table has no per-row
constraint a valid action can trip: only ``action_type``/``ok`` are NOT NULL and
both are always supplied) and assert the log severity by write-mode. The
executor is built via ``__new__`` to skip registry-priming ``__init__``,
mirroring test_executor_artifact_type_refusal.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition
from shared.action_types import ActionResult


# ID: 4f6b1d2e-8c0a-4e91-9b27-3a5f7c1e0d84
async def _noop_executor(**_kwargs) -> ActionResult:
    """Never invoked — _audit_log is called directly, not via execute()."""
    return ActionResult(action_id="test.audit_gap", ok=True, data={}, duration_sec=0.0)


def _definition() -> ActionDefinition:
    """A dangerous-impact stub definition; only action_id/impact_level are read."""
    return ActionDefinition(
        action_id="test.audit_gap",
        description="#634 audit-gap test fixture",
        category=ActionCategory.FIX,
        policies=[],
        executor=_noop_executor,
        impact_level="dangerous",
    )


def _executor_with_failing_session() -> ActionExecutor:
    """ActionExecutor whose session factory raises — simulates DB unavailability."""
    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.core_context.registry.session = MagicMock(
        side_effect=RuntimeError("DB unavailable")
    )
    return executor


@pytest.mark.asyncio
async def test_write_action_audit_failure_is_error_with_marker() -> None:
    """#634: write=True audit failure → ERROR carrying the AUDIT_GAP marker."""
    executor = _executor_with_failing_session()
    result = ActionResult(
        action_id="test.audit_gap", ok=True, data={}, duration_sec=0.01
    )

    with patch("body.atomic.executor.logger") as mock_logger:
        await executor._audit_log(_definition(), result, write=True)

    mock_logger.error.assert_called_once()
    assert "AUDIT_GAP" in mock_logger.error.call_args[0][0]
    mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_read_action_audit_failure_stays_warning() -> None:
    """Reads remain a quiet best-effort warning — no ERROR, no AUDIT_GAP."""
    executor = _executor_with_failing_session()
    result = ActionResult(
        action_id="test.audit_gap", ok=True, data={}, duration_sec=0.01
    )

    with patch("body.atomic.executor.logger") as mock_logger:
        await executor._audit_log(_definition(), result, write=False)

    mock_logger.warning.assert_called_once()
    mock_logger.error.assert_not_called()
