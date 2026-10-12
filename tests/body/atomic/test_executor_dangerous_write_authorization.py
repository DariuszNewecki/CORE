# tests/body/atomic/test_executor_dangerous_write_authorization.py
"""ActionExecutor refuses a dangerous write that no governor approval carries (#633).

The inline authorization check used to return ``authorized: True`` always. Now
a ``dangerous`` action in write mode runs only inside the approval scope of a
proposal the governor approved; dry runs and non-dangerous actions are
unaffected. Refusal is proven through execute(): the action body is a trap
that fails the test if dispatch reaches it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition, ActionRegistry
from shared.action_types import ActionResult
from shared.governance_token import approval_scope


class _DispatchReached(AssertionError):
    """Raised if a refused action's body runs anyway."""


async def _trap(**_kwargs) -> ActionResult:
    raise _DispatchReached("a refused dangerous write reached the action body")


def _executor(impact_level: str) -> ActionExecutor:
    registry = ActionRegistry()
    registry.register(
        ActionDefinition(
            action_id="test.dangerous_write",
            description="authorization test fixture",
            category=ActionCategory.CHECK,
            policies=[],
            executor=_trap,
            impact_level=impact_level,
        )
    )
    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.registry = registry
    executor._sandbox = MagicMock()
    return executor


@pytest.mark.parametrize(
    "authority",
    [None, "risk_classification.safe_auto_approval"],
    ids=["no-proposal", "auto-approved"],
)
async def test_dangerous_write_without_governor_approval_is_refused(
    authority: str | None,
) -> None:
    executor = _executor("dangerous")
    with approval_scope(authority):
        result = await executor.execute(action_id="test.dangerous_write", write=True)
    assert result.ok is False
    assert result.data["error"] == "Authorization failed"
    details = result.data["details"]
    assert details["authorized"] is False
    assert details["approval_authority"] == authority
    assert "governor approved" in details["reason"]


def test_governor_approved_dangerous_write_is_authorized() -> None:
    executor = _executor("dangerous")
    definition = executor.registry.get("test.dangerous_write")
    with approval_scope("principal.governor"):
        check = executor._check_authorization(definition, write=True)
    assert check["authorized"] is True


@pytest.mark.parametrize(
    ("impact_level", "write"),
    [("dangerous", False), ("moderate", True), ("safe", True)],
)
def test_dry_runs_and_non_dangerous_actions_are_unaffected(
    impact_level: str, write: bool
) -> None:
    executor = _executor(impact_level)
    definition = executor.registry.get("test.dangerous_write")
    assert executor._check_authorization(definition, write=write)["authorized"]
