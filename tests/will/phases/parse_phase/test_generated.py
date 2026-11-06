from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.phases.parse_phase import ParsePhase


# ID: c198690e-e2c6-4821-ac86-15c59eeaceeb
async def test_ParsePhase_execute() -> None:
    # Build a ParsePhase instance without running the real constructor, so no
    # external I/O (git_service / cognitive_service / qdrant) is required.
    phase = ParsePhase.__new__(ParsePhase)

    # Reconnoitre returns (text, data) tuple.
    phase._reconnoitre = AsyncMock(return_value=("recon text", {"files": ["a.py"]}))

    # Planner returns a non-empty plan (a list of steps).
    step = MagicMock()
    step.action = "read_file"
    step.step = "inspect"
    plan = [step]
    phase._planner = MagicMock()
    phase._planner.create_execution_plan = AsyncMock(return_value=plan)

    # Decision records helper.
    phase._decision_records = MagicMock(return_value={"decisions": []})

    context = MagicMock()
    context.goal = "make it faster"
    context.workflow_type = "developer"
    context.results = {}

    result = await phase.execute(context)

    assert result.ok is True
    assert result.name == "parse"
    assert result.data["goal"] == "make it faster"
    assert result.data["steps_count"] == 1
    assert result.data["execution_plan"] is plan
    assert context.results["parse"] is result.data
    assert context.results["planning"] is result.data

    phase._reconnoitre.assert_awaited_once()
    phase._planner.create_execution_plan.assert_awaited_once_with(
        "make it faster", "recon text"
    )
