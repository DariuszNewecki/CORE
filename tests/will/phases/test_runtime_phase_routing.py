# tests/will/phases/test_runtime_phase_routing.py

"""Runtime routing is exhaustive and fails closed (#895 U2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from shared.models.workflow_models import PhaseResult
from will.phases.runtime_phase import _WORKFLOW_ROUTING, RuntimePhase


class _StubWorkflowContext:
    def __init__(self, workflow_type: str) -> None:
        self.goal = "do the thing"
        self.workflow_type = workflow_type
        self.write = False
        self.results: dict[str, Any] = {}


def _phase() -> RuntimePhase:
    with (
        patch("will.phases.runtime_phase.CodeGenerationPhase"),
        patch("will.phases.runtime_phase.TestGenerationPhase"),
        patch("will.phases.runtime_phase.InvestigationPhase"),
    ):
        return RuntimePhase(core_context=object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_unknown_workflow_fails_closed_instead_of_generating_code() -> None:
    """The old default routed anything unrecognised to code generation."""
    phase = _phase()

    result = await phase.execute(_StubWorkflowContext("not_a_workflow"))  # type: ignore[arg-type]

    assert result.ok is False
    assert result.error.startswith("UNAVAILABLE:")
    assert "no declared runtime routing" in result.error


@pytest.mark.asyncio
async def test_evaluation_routes_to_investigation_never_generation() -> None:
    phase = _phase()
    phase._investigation.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=PhaseResult(name="runtime", ok=True, data={"findings": []})
    )
    phase._code_gen.execute = AsyncMock()  # type: ignore[method-assign]
    phase._test_gen.execute = AsyncMock()  # type: ignore[method-assign]

    result = await phase.execute(_StubWorkflowContext("evaluation"))  # type: ignore[arg-type]

    assert result.ok is True
    phase._investigation.execute.assert_awaited_once()
    phase._code_gen.execute.assert_not_awaited()
    phase._test_gen.execute.assert_not_awaited()


def test_evaluation_declares_no_generating_sub_phase() -> None:
    assert _WORKFLOW_ROUTING["evaluation"] == ["investigation"]


def test_workflows_that_relied_on_the_old_default_are_listed_explicitly() -> None:
    """Closing the fallback must not change their behaviour."""
    for workflow in ("full_feature_development", "core.change_set.lifecycle"):
        assert _WORKFLOW_ROUTING[workflow] == ["code_generation"]
