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
