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


import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


# ID: fcc3b2ad-9da7-4a94-bfd7-b3c235834c4d
def test_ParsePhase():
    core_context = MagicMock()
    core_context.git_service.repo_path = "/tmp/repo"
    core_context.cognitive_service = MagicMock()
    core_context.qdrant_service = MagicMock()

    recon_root = Path("/tmp/repo")
    recon_scope = {"mode": "snapshot"}

    step = SimpleNamespace(action="read", step="inspect file")
    plan = [step]

    mock_planner = MagicMock()
    mock_planner.create_execution_plan = AsyncMock(return_value=plan)
    mock_planner.tracer = None

    mock_recon = MagicMock()
    mock_recon.execute = AsyncMock(
        return_value=SimpleNamespace(
            ok=True,
            data={
                "recon_text": "target has 2 files",
                "recon_digest": "digest-abc",
                "recon_raw": {"file_count": 2},
                "unavailable": [],
            },
        )
    )

    with (
        patch(
            "will.phases.parse_phase.PlannerAgent", return_value=mock_planner
        ) as planner_cls,
        patch(
            "will.phases.parse_phase.evaluation_view",
            return_value=(recon_root, recon_scope),
        ),
        patch(
            "will.phases.parse_phase.TargetReconnaissanceAnalyzer",
            return_value=mock_recon,
        ),
    ):
        phase = ParsePhase(core_context)

    planner_cls.assert_called_once_with(
        cognitive_service=core_context.cognitive_service,
        repo_path=Path("/tmp/repo"),
        qdrant_service=core_context.qdrant_service,
    )

    wf_context = MagicMock()
    wf_context.goal = "make it faster"
    wf_context.workflow_type = "implementation"
    wf_context.results = {}

    result = asyncio.run(phase.execute(wf_context))

    assert result.ok is True
    assert result.name == "parse"
    mock_planner.create_execution_plan.assert_awaited_once_with(
        "make it faster", "target has 2 files"
    )
    assert wf_context.results["parse"]["steps_count"] == 1
    assert wf_context.results["planning"] is wf_context.results["parse"]
    assert wf_context.results["parse"]["execution_plan"] == plan
    assert result.data["reconnaissance"]["available"] is True
    assert result.data["reconnaissance"]["view"] == recon_scope
    assert result.data["decisions"] == []
