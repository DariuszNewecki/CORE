from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 9cd319d3-3ba3-492b-9d9c-4fe2144e61fd
async def test_GoalExecutionWorker_run():
    from will.workers.goal_execution_worker import GoalExecutionWorker

    context = MagicMock()
    context.qdrant_service = MagicMock()
    context.path_resolver = MagicMock()
    context.target_binding = None
    context.registry = MagicMock()
    context.registry.get_qdrant_service = AsyncMock(return_value=MagicMock())

    worker = GoalExecutionWorker(
        context=context,
        goal="do the thing",
        workflow_type="develop",
        write=False,
        task_id=None,
    )

    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.post_unavailable = AsyncMock()
    worker.post_finding = AsyncMock()

    activity = MagicMock()
    activity.run_id = "run-123"
    activity_cm = MagicMock()
    activity_cm.__enter__ = MagicMock(return_value=activity)
    activity_cm.__exit__ = MagicMock(return_value=False)

    phase = SimpleNamespace(
        name="parse", ok=True, duration_sec=1.0, error=None, data={}
    )
    fake_result = SimpleNamespace(
        ok=True,
        phase_results=[phase],
        workflow_type="develop",
        total_duration=1.0,
    )

    orchestrator = MagicMock()
    orchestrator.execute_goal = AsyncMock(return_value=fake_result)

    with (
        patch(
            "will.workers.goal_execution_worker.activity_run",
            return_value=activity_cm,
        ),
        patch(
            "will.workers.goal_execution_worker.resolve_brain_services",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.probe_planner_readiness",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.PhaseRegistry",
            return_value=MagicMock(),
        ),
        patch(
            "will.workers.goal_execution_worker.WorkflowOrchestrator",
            return_value=orchestrator,
        ),
        patch(
            "will.workers.goal_execution_worker.post_reconnaissance_records",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.post_decision_records",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.post_finding_records",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.blackboard_safe",
            side_effect=lambda x: x,
        ),
    ):
        await worker.run()

    assert worker.run_id == "run-123"
    assert worker.result is fake_result
    orchestrator.execute_goal.assert_awaited_once_with(
        goal="do the thing", workflow_type="develop", write=False
    )
    worker.post_report.assert_any_await(
        "goal_run.run-123.start",
        unittest_any_start_payload := worker.post_report.await_args_list[0].args[1],
    )
    assert unittest_any_start_payload["run_id"] == "run-123"
    assert unittest_any_start_payload["goal"] == "do the thing"
    outcome_calls = [
        c
        for c in worker.post_report.await_args_list
        if c.args[0] == "goal_run.run-123.outcome"
    ]
    assert len(outcome_calls) == 1
    assert outcome_calls[0].args[1]["ok"] is True
    worker.post_unavailable.assert_not_awaited()




# ID: 915a254a-8ce4-47ff-afc5-c88bef840026
def test_GoalExecutionWorker():
    from will.workers.goal_execution_worker import GoalExecutionWorker

    context = MagicMock()
    context.qdrant_service = MagicMock()
    context.path_resolver = MagicMock()
    context.target_binding = None

    with (
        patch(
            "will.workers.goal_execution_worker.Worker.__init__", return_value=None
        ) as mock_super_init,
        patch(
            "will.workers.goal_execution_worker.resolve_brain_services",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.probe_planner_readiness",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.goal_execution_worker.PhaseRegistry",
        ) as mock_phase_registry_cls,
        patch(
            "will.workers.goal_execution_worker.WorkflowOrchestrator",
        ) as mock_orchestrator_cls,
    ):
        mock_phase_registry_cls.return_value = MagicMock()

        orchestrator = MagicMock()
        orchestrator.execute_goal = AsyncMock(return_value=MagicMock(ok=True))
        mock_orchestrator_cls.return_value = orchestrator

        worker = GoalExecutionWorker(
            context=context,
            goal="Add a feature",
            workflow_type="feature",
            write=False,
            task_id="task-1",
            create_proposal_only=False,
            probes=False,
        )

        mock_super_init.assert_called_once()

    assert worker.goal == "Add a feature"
    assert worker.workflow_type == "feature"
    assert worker.write is False
    assert worker.task_id == "task-1"
    assert worker.create_proposal_only is False
    assert worker.probes is False
    assert worker.probe_records == []
    assert worker.run_id is None
    assert worker.result is None
    assert worker.unavailable_reason is None
    assert worker.proposal_id is None
    assert worker.proposal_approval_required is None
