from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.orchestration.workflow_orchestrator import WorkflowOrchestrator


# ID: b3bbc066-5ab8-412a-aa28-9b5ddc22cf1c
async def test_WorkflowOrchestrator_execute_goal():
    phase_registry = MagicMock()
    path_resolver = MagicMock()

    with (
        patch("will.orchestration.workflow_orchestrator.DecisionTracer"),
        patch("will.orchestration.workflow_orchestrator.get_intent_repository"),
    ):
        orchestrator = WorkflowOrchestrator(phase_registry, path_resolver)

    phase_result = MagicMock()
    phase_result.ok = True
    phase_result.data = {"done": True}
    phase_result.error = None
    phase_result.name = "discover"
    phase_result.duration_sec = 0.0

    phase = MagicMock()
    phase.execute = AsyncMock(return_value=phase_result)
    phase_registry.get.return_value = phase

    workflow_def = MagicMock()
    workflow_def.write_required = False
    workflow_def.phases = ["discover"]
    workflow_def.success_criteria = {"all": True}

    orchestrator._load_workflow_definition = MagicMock(return_value=workflow_def)
    orchestrator._load_phase_definition = MagicMock(return_value={"failure_modes": {}})
    orchestrator._evaluate_success_criteria = MagicMock(return_value=True)

    result = await orchestrator.execute_goal(
        goal="ship it", workflow_type="standard", write=False
    )

    assert result.ok is True
    assert result.workflow_type == "standard"
    assert result.phase_results == [phase_result]
    phase.execute.assert_awaited_once()
    phase_registry.get.assert_called_once_with("discover")
    orchestrator._evaluate_success_criteria.assert_called_once_with(
        {"all": True},
        result and orchestrator._evaluate_success_criteria.call_args[0][1],
    )




# ID: d3810e1c-2860-45f5-91fc-126c5d46fc1a
def test_WorkflowOrchestrator():
    from will.orchestration.workflow_orchestrator import WorkflowOrchestrator

    phase_registry = MagicMock()
    path_resolver = MagicMock()

    mock_repo = MagicMock()

    with (
        patch(
            "will.orchestration.workflow_orchestrator.get_intent_repository",
            return_value=mock_repo,
        ),
        patch(
            "will.orchestration.workflow_orchestrator.DecisionTracer",
        ),
    ):
        orchestrator = WorkflowOrchestrator(phase_registry, path_resolver)

    assert orchestrator.phases is phase_registry
    assert orchestrator._paths is path_resolver
    assert orchestrator._intent_repo is mock_repo

    mock_repo.load_workflow.return_value = {
        "workflow_id": "feature",
        "description": "A feature workflow",
        "stages": [
            {"stage_id": "interpret.intent", "order": 0},
            {"stage_id": "audit.sandbox", "order": 1},
            {"stage_id": "interpret.again", "order": 2},
        ],
        "success_criteria": {},
        "write_required": True,
        "dangerous": False,
        "timeout_minutes": 30,
    }

    workflow_def = orchestrator._load_workflow_definition("feature")

    mock_repo.load_workflow.assert_called_once_with("feature")
    assert workflow_def.workflow_type == "feature"
    assert workflow_def.description == "A feature workflow"
    assert workflow_def.phases == ["interpret", "audit"]
    assert workflow_def.write_required is True
