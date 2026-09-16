# tests/body/atomic/test_executor_governed_refusal_surfacing.py

"""ActionExecutor surfaces a governed refusal's rule_id and structured payload.

#895 U3 D2: when an action raises an exception that names its governing rule
(FileHandler's RepositoryBoundaryViolationError for
architecture.execution_write.repository_containment), the executor's failure
ActionResult carries ``rule_id`` and ``refusal`` in ``data`` -- the ADR-159
I-5 probe records the rule that refused, not just an exception class name.
An ordinary exception still yields only ``error`` / ``error_type``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition, ActionRegistry
from shared.action_types import ActionResult
from shared.exceptions import RepositoryBoundaryViolationError


async def _raise_boundary(**_kwargs) -> ActionResult:
    raise RepositoryBoundaryViolationError("/subject/x.py", "/evidence/copy")


async def _raise_plain(**_kwargs) -> ActionResult:
    raise RuntimeError("plain failure")


def _definition(action_id: str, executor) -> ActionDefinition:
    return ActionDefinition(
        action_id=action_id,
        description="refusal surfacing fixture",
        category=ActionCategory.CHECK,
        policies=[],
        executor=executor,
        impact_level="safe",
    )


def _executor(registry: ActionRegistry) -> ActionExecutor:
    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.registry = registry
    sandbox = MagicMock()
    sandbox.build_execution_context.return_value = (executor.core_context, None)
    executor._sandbox = sandbox
    # the audit log writes ActionResult.data to the DB; not under test here
    executor._audit_log = AsyncMock()  # type: ignore[method-assign]
    return executor


async def test_governed_refusal_carries_rule_id_and_payload() -> None:
    registry = ActionRegistry()
    registry.register(_definition("test.boundary", _raise_boundary))
    result = await _executor(registry).execute(action_id="test.boundary")

    assert result.ok is False
    assert result.data["error_type"] == "RepositoryBoundaryViolationError"
    assert (
        result.data["rule_id"] == "architecture.execution_write.repository_containment"
    )
    assert result.data["refusal"]["attempted_path"] == "/subject/x.py"
    assert result.data["refusal"]["bound_root"] == "/evidence/copy"
    assert "escape repository boundary" in result.data["error"]


async def test_plain_exception_has_no_rule_id() -> None:
    registry = ActionRegistry()
    registry.register(_definition("test.plain", _raise_plain))
    result = await _executor(registry).execute(action_id="test.plain")

    assert result.ok is False
    assert result.data["error_type"] == "RuntimeError"
    assert "rule_id" not in result.data and "refusal" not in result.data
