# tests/body/atomic/test_executor_artifact_type_refusal.py
"""F-43 negative-path refusal test (ADR-092 D1 mandatory verification).

ADR-092 D1's load-bearing claim is **refusal**: the ActionExecutor rejects
dispatch of an action whose declared artifact_type is not registered in the
F-41 IntentRepository. The closing F-43 test MUST exercise the rejection
path (a happy-path test that dispatches a Python action against the
registered `python` type satisfies neither D1's wording nor its intent).

This test constructs a stub ActionDefinition declaring an unregistered
artifact_type (`unregistered_artifact_type_xyz`), wires it into a real
ActionRegistry, instantiates ActionExecutor via __new__ (mirroring the
pattern in test_executor_worktree_isolation.py to bypass registry-priming
__init__), and asserts that execute() refuses dispatch with a structured
error citing the constitutional basis (ADR-091 D6 item 3, ADR-092 D1).

The action's executor callable is intentionally instrumented: if dispatch
were to reach it, the test fails loudly via a sentinel side effect.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition, ActionRegistry
from shared.action_types import ActionResult


# ID: 0a97a6fa-1bcf-4063-af54-8225a6f31517
class _DispatchReached(AssertionError):
    """Raised by the stub executor if the refusal chokepoint failed to block."""


# ID: 23363781-874e-49af-82f2-2e0000e47e44
async def _trap_executor(**_kwargs) -> ActionResult:
    """Stub action executor that fails if dispatch reaches it.

    ADR-092 D1's refusal must short-circuit before this is called. Any
    invocation indicates the chokepoint was bypassed — a test failure.
    """
    raise _DispatchReached(
        "ActionExecutor reached the action executor despite the action "
        "declaring an unregistered artifact_type. ADR-092 D1 refusal "
        "chokepoint was bypassed."
    )


# ID: 791bcca7-1b81-42a7-b81d-940f0836ca0f
def _stub_definition(artifact_type: tuple[str, ...]) -> ActionDefinition:
    """Build an ActionDefinition declaring the given artifact_type tuple."""
    return ActionDefinition(
        action_id="test.f43_refusal",
        description="F-43 refusal-path test fixture",
        category=ActionCategory.CHECK,
        policies=[],
        executor=_trap_executor,
        impact_level="safe",
        artifact_type=artifact_type,
    )


# ID: f56fa5f9-785c-4b2f-902e-eb3bd25f4eaf
async def test_executor_refuses_dispatch_on_unregistered_artifact_type() -> None:
    """ADR-092 D1: action declaring unregistered artifact_type → refused dispatch.

    Wires a stub ActionDefinition declaring artifact_type=
    ("unregistered_artifact_type_xyz",) into a real ActionRegistry,
    instantiates ActionExecutor via __new__ to skip registry-priming init,
    and asserts execute() returns an ActionResult(ok=False) citing the
    unregistered artifact_type and the constitutional basis. The stub
    executor (_trap_executor) raises _DispatchReached if invoked — its
    absence confirms the chokepoint short-circuited before dispatch.
    """
    registry = ActionRegistry()
    registry.register(_stub_definition(("unregistered_artifact_type_xyz",)))

    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.registry = registry
    executor._sandbox = MagicMock()

    result = await executor.execute(action_id="test.f43_refusal")

    assert result.ok is False, (
        "ActionExecutor must refuse dispatch when declared artifact_type is "
        "not in the F-41 IntentRepository registry (ADR-092 D1)."
    )
    assert result.data["error"] == "Action declared unregistered artifact_type"
    assert result.data["unregistered_artifact_types"] == [
        "unregistered_artifact_type_xyz"
    ]
    assert "python" in result.data["registered_artifact_types"], (
        "Sanity check: the F-41 registry should at minimum contain `python`."
    )
    assert "ADR-091 D6 item 3" in result.data["constitutional_basis"]
    assert "ADR-092 D1" in result.data["constitutional_basis"]
