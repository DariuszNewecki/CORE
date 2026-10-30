from __future__ import annotations

from will.autonomy.autonomous_developer import infer_workflow_type


# ID: b3e2f32a-5e64-4755-bc01-cb2f84ec4c97
def test_infer_workflow_type():
    assert (
        infer_workflow_type("Refactor the auth module into smaller pieces")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Extract helper methods from the service")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Split the large class into modules")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Generate tests for the parser") == "coverage_remediation"
    )
    assert (
        infer_workflow_type("Improve test coverage of the utils")
        == "coverage_remediation"
    )
    assert infer_workflow_type("Do something completely vague") == "refactor_modularity"


from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.autonomous_developer import develop_from_goal


# ID: ade8456d-e2f4-47d6-b674-f8d390c6b91d
async def test_develop_from_goal() -> None:
    context = MagicMock()

    phase_result = MagicMock()
    phase_result.ok = True
    phase_result.name = "plan"

    result = MagicMock()
    result.ok = True
    result.phase_results = [phase_result]

    fake_worker = MagicMock()
    fake_worker.result = result
    fake_worker.unavailable_reason = None
    fake_worker.probe_records = []
    fake_worker.run_id = "run-123"
    fake_worker.proposal_id = None
    fake_worker.proposal_approval_required = False
    fake_worker.start = AsyncMock()

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=fake_worker,
    ) as worker_cls:
        success, message = await develop_from_goal(
            context,
            "Improve modularity of user_service.py",
            "refactor_modularity",
            write=False,
        )

    assert success is True
    assert "refactor_modularity" in message
    assert "run-123" in message
    fake_worker.start.assert_awaited_once()
    worker_cls.assert_called_once()
    _, kwargs = worker_cls.call_args
    assert kwargs["create_proposal_only"] is False
    assert kwargs["goal"] == "Improve modularity of user_service.py"
    assert kwargs["workflow_type"] == "refactor_modularity"
