"""Tests for the **kwargs constitutional invariant in the @atomic_action decorator.

Established by issue #448 after the FlowExecutor consumes-None default flip
in #445 exposed that 14/42 @atomic_action functions lacked **kwargs and would
TypeError at runtime when forwarded extra keyword arguments. The check fires
at decoration (import) time and refuses to wrap any function whose signature
does not include Parameter.VAR_KEYWORD.

The check lives in @atomic_action (not in the registry's
_validate_action_signature) because every @atomic_action function — whether
or not it also carries @register_action — is a target of the FlowExecutor /
ActionExecutor kwargs-forwarding contract.
"""

from __future__ import annotations

import pytest

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


# ID: 9021c28e-cf79-4f22-a1ae-b6420d23fccb
def test_action_with_kwargs_decorates_successfully() -> None:
    """A function whose signature includes **kwargs is wrapped without error."""

    @atomic_action(
        action_id="test.kwargs_ok",
        intent="Test that kwargs-accepting functions decorate",
        impact=ActionImpact.READ_ONLY,
        policies=["test.policy"],
    )
    async def action_kwargs_ok(**kwargs) -> ActionResult:
        return ActionResult(action_id="test.kwargs_ok", ok=True, data={})

    assert hasattr(action_kwargs_ok, "__wrapped__") or callable(action_kwargs_ok)


# ID: 8feaeff1-d17e-428b-a690-9bb7e0a0b645
def test_action_without_kwargs_refused_at_decoration() -> None:
    """A function without **kwargs raises TypeError at decoration time."""

    with pytest.raises(TypeError, match="must accept \\*\\*kwargs"):

        @atomic_action(
            action_id="test.kwargs_missing",
            intent="Test that kwargs-less functions are refused",
            impact=ActionImpact.READ_ONLY,
            policies=["test.policy"],
        )
        async def action_kwargs_missing(file_path: str) -> ActionResult:
            return ActionResult(action_id="test.kwargs_missing", ok=True, data={})


# ID: 12b5f894-b27c-49a6-8923-b786722e74eb
def test_action_with_args_only_still_refused() -> None:
    """*args without **kwargs does NOT satisfy the invariant — keyword
    forwarding is the failure mode #445 exposed, not positional forwarding.
    """

    with pytest.raises(TypeError, match="must accept \\*\\*kwargs"):

        @atomic_action(
            action_id="test.args_only",
            intent="Test that *args-only signatures are refused",
            impact=ActionImpact.READ_ONLY,
            policies=["test.policy"],
        )
        async def action_args_only(*args) -> ActionResult:
            return ActionResult(action_id="test.args_only", ok=True, data={})
