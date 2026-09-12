# tests/will/autonomy/test_develop_from_goal_worker_shim.py
"""develop_from_goal preserves its (bool, str) return contract now that it
is a thin shim over GoalExecutionWorker (#872, ADR-159 D4).

No real Worker lifecycle here — GoalExecutionWorker itself is mocked at its
import site; its own lifecycle/evidence behavior is covered by
tests/will/workers/test_goal_execution_worker.py. This file only proves the
shim's contract: same construction, same (bool, str) shape, exceptions from
start() still translate to (False, "Execution error: ...").
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from will.autonomy.autonomous_developer import develop_from_goal


def _fake_worker(
    result: PhaseWorkflowResult,
    run_id: str = "rid-1",
    proposal_id: str | None = None,
    proposal_approval_required: bool | None = None,
) -> MagicMock:
    worker = MagicMock()
    worker.start = AsyncMock()
    worker.result = result
    worker.run_id = run_id
    worker.proposal_id = proposal_id
    worker.proposal_approval_required = proposal_approval_required
    return worker


async def test_success_return_contract_includes_run_id() -> None:
    result = PhaseWorkflowResult(
        ok=True, phase_results=[PhaseResult(name="execution", ok=True)]
    )
    worker = _fake_worker(result)

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ) as worker_cls:
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
            write=True,
            task_id="task-1",
        )

    assert ok is True
    assert "completed successfully" in message
    assert "run_id=rid-1" in message
    worker_cls.assert_called_once()
    _, kwargs = worker_cls.call_args
    assert kwargs["goal"] == "Improve modularity of demo.py"
    assert kwargs["workflow_type"] == "refactor_modularity"
    assert kwargs["write"] is True
    assert kwargs["task_id"] == "task-1"
    # ADR-160 D3: a caller that omits create_proposal_only gets today's
    # unchanged behavior -- this is the regression proof for the four
    # unconverted callers (effects.py, refactor_runner.py,
    # modularity_remediation_service.py, the CLI), which all call
    # develop_from_goal without this kwarg.
    assert kwargs["create_proposal_only"] is False


async def test_failure_return_contract_names_failed_phase() -> None:
    result = PhaseWorkflowResult(
        ok=False,
        phase_results=[
            PhaseResult(name="interpret", ok=True),
            PhaseResult(name="audit", ok=False, error="canary failed"),
        ],
    )
    worker = _fake_worker(result, run_id="rid-2")

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ):
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
        )

    assert ok is False
    assert "audit" in message
    assert "run_id=rid-2" in message


async def test_worker_start_exception_returns_false_with_error_message() -> None:
    worker = MagicMock()
    worker.start = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ):
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
        )

    assert ok is False
    assert message == "Execution error: boom"


# ------------------------------------------------- create_proposal_only (ADR-160 D3)


async def test_create_proposal_only_success_message_names_pending_proposal() -> None:
    """The message must not claim work is running or completed -- it names
    the created Proposal as pending Governor approval."""
    result = PhaseWorkflowResult(
        ok=True,
        phase_results=[PhaseResult(name="create_proposal", ok=True)],
    )
    worker = _fake_worker(
        result,
        run_id="rid-3",
        proposal_id="proposal-abc",
        proposal_approval_required=True,
    )

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ) as worker_cls:
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Fix the thing",
            workflow_type="code_modification",
            write=True,
            create_proposal_only=True,
        )

    assert ok is True
    assert "proposal-abc" in message
    assert "pending Governor approval" in message
    assert "completed" not in message
    assert "running" not in message
    assert "approval_required=True" in message
    _, kwargs = worker_cls.call_args
    assert kwargs["create_proposal_only"] is True


async def test_create_proposal_only_refusal_message_names_reason_not_a_normal_failure() -> (
    None
):
    result = PhaseWorkflowResult(
        ok=False,
        phase_results=[
            PhaseResult(
                name="create_proposal",
                ok=False,
                error="workflow_type 'refactor_modularity' does not execute the planned tasks",
            )
        ],
    )
    worker = _fake_worker(result, run_id="rid-4")

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ):
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Refactor for modularity",
            workflow_type="refactor_modularity",
            write=True,
            create_proposal_only=True,
        )

    assert ok is False
    assert "could not be converted to a Proposal" in message
    assert "does not execute the planned tasks" in message
