# tests/will/phases/test_load_phase__plan_resolution.py

"""LoadPhase resolves the parse phase's plan under either key.

``execution_plan`` (code workflows, list[ExecutionTask]) or
``investigation_plan`` (the #895 U2 evaluation workflow, list[InvestigationStep]).
The 2026-09-17 cold run against a disposable target failed at LOAD with "No
execution plan available from parse phase." on every evaluation run because
only the first key was read.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from will.agents.investigation_planner import InvestigationStep
from will.phases.load_phase import LoadPhase


def _phase() -> LoadPhase:
    ctx = SimpleNamespace(
        cognitive_service=object(), file_handler=object(), git_service=object()
    )
    return LoadPhase(ctx)  # type: ignore[arg-type]


def _context(parse_data: dict, workflow_type: str) -> SimpleNamespace:
    return SimpleNamespace(
        results={"parse": parse_data}, write=False, workflow_type=workflow_type
    )


@pytest.mark.asyncio
async def test_load_accepts_investigation_plan_for_evaluation() -> None:
    steps = [InvestigationStep("1", "inspect.layout", {})]
    result = await _phase().execute(
        _context({"investigation_plan": steps}, "evaluation")  # type: ignore[arg-type]
    )
    assert result.ok, result.error
    assert result.data["steps"] == 1
    assert result.data["workflow_type"] == "evaluation"


@pytest.mark.asyncio
async def test_load_still_accepts_execution_plan() -> None:
    result = await _phase().execute(
        _context({"execution_plan": [object(), object()]}, "code_modification")  # type: ignore[arg-type]
    )
    assert result.ok and result.data["steps"] == 2


@pytest.mark.asyncio
async def test_load_refuses_when_neither_plan_is_present() -> None:
    result = await _phase().execute(_context({"goal": "g"}, "evaluation"))  # type: ignore[arg-type]
    assert not result.ok
    assert result.error == "No execution plan available from parse phase."
