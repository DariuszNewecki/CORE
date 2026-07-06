# tests/will/phases/test_interpret_phase__InterpretPhase.py
"""InterpretPhase — workflow type inference and explicit-override contract.

Covers:
  - Explicit workflow_type from WorkflowContext passes through without inference
  - Unknown explicit workflow_type returns ok=False
  - Inference: refactor keywords → refactor_modularity
  - Inference: test/coverage keywords → coverage_remediation
  - Inference: implement/create/fix keywords → code_modification (not full_feature_development)
  - Default (no keyword match) → code_modification
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from will.phases.interpret_phase import InterpretPhase


def _ctx() -> MagicMock:
    return MagicMock(name="CoreContext")


def _wctx(goal: str, workflow_type: str | None = None) -> MagicMock:
    wctx = MagicMock(name="WorkflowContext")
    wctx.goal = goal
    wctx.workflow_type = workflow_type
    return wctx


# ID: def2055d-c5d3-411e-8afe-a4abbc5962cb
async def test_explicit_workflow_type_passes_through() -> None:
    """Explicit workflow_type skips inference and maps to the stated type."""
    phase = InterpretPhase(_ctx())
    result = await phase.execute(_wctx("do stuff", workflow_type="coverage_remediation"))
    assert result.ok is True
    assert result.data["workflow_type"] == "coverage_remediation"
    assert result.data["_metadata"]["interpretation_method"] == "explicit"


# ID: ddd7a3d0-7aea-4377-8592-f1ce031dd4a4
async def test_unknown_explicit_workflow_type_returns_error() -> None:
    """An unknown explicit workflow_type is rejected with ok=False."""
    phase = InterpretPhase(_ctx())
    result = await phase.execute(_wctx("do stuff", workflow_type="full_feature_development"))
    assert result.ok is False
    assert "full_feature_development" in (result.error or "")


# ID: d8348cd8-e371-4682-b20d-b8ccb78b5db4
@pytest.mark.parametrize(
    "goal,expected",
    [
        ("refactor the payments module", "refactor_modularity"),
        ("split this large file into submodules", "refactor_modularity"),
        ("add tests for the executor", "coverage_remediation"),
        ("improve test coverage for body services", "coverage_remediation"),
        ("implement the new feature", "code_modification"),
        ("create a new endpoint handler", "code_modification"),
        ("fix the broken import", "code_modification"),
        ("build the missing validator", "code_modification"),
    ],
)
async def test_workflow_type_inference(goal: str, expected: str) -> None:
    """Inference maps keyword patterns to the correct workflow type."""
    phase = InterpretPhase(_ctx())
    result = await phase.execute(_wctx(goal))
    assert result.ok is True
    assert result.data["workflow_type"] == expected


# ID: 25312684-6207-4d25-bd13-daa70005acc6
async def test_default_inference_returns_code_modification() -> None:
    """A goal with no recognisable keywords defaults to code_modification."""
    phase = InterpretPhase(_ctx())
    result = await phase.execute(_wctx("update the governance metadata"))
    assert result.ok is True
    assert result.data["workflow_type"] == "code_modification"


# ID: 2204de9e-a9b4-4783-bbcf-6fd7aba3feee
async def test_full_feature_development_not_inferred() -> None:
    """full_feature_development is never returned by inference — it was removed."""
    phase = InterpretPhase(_ctx())
    goals = [
        "implement a new feature",
        "build the auth system",
        "develop the API",
        "create the dashboard component",
    ]
    for goal in goals:
        result = await phase.execute(_wctx(goal))
        assert result.ok is True
        assert result.data["workflow_type"] != "full_feature_development", (
            f"Goal '{goal}' returned full_feature_development"
        )
