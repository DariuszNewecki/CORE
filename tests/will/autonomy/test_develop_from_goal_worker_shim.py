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
    # #894 Unit 3: the shim checks this first; a bare MagicMock attribute is
    # truthy and would read as "unavailable". A ready worker leaves it None.
    worker.unavailable_reason = None
    return worker


async def test_success_return_contract_includes_run_id() -> None:
    """A grandfathered direct-write caller (legacy_direct_write=True) still
    gets the plain "completed successfully" message -- this caller shape is
    unaffected by the ADR-160 D3 polarity inversion, only its opt-out
    became explicit."""
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
            legacy_direct_write=True,
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
    assert kwargs["create_proposal_only"] is False


async def test_fail_closed_default_write_true_reaches_worker_as_create_proposal_only() -> (
    None
):
    """ADR-160 D3 polarity inversion, the fail-closed default itself: a
    caller that omits legacy_direct_write and requests write=True reaches
    GoalExecutionWorker with create_proposal_only=True
    (`create_proposal_only = write and not legacy_direct_write`)."""
    result = PhaseWorkflowResult(
        ok=True,
        phase_results=[PhaseResult(name="create_proposal", ok=True)],
    )
    worker = _fake_worker(result, proposal_id="proposal-default")

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ) as worker_cls:
        await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
            write=True,
        )

    _, kwargs = worker_cls.call_args
    assert kwargs["create_proposal_only"] is True


async def test_legacy_direct_write_true_preserves_direct_write_behavior() -> None:
    """A grandfathered caller passing legacy_direct_write=True keeps
    create_proposal_only=False even for a write-capable request -- the
    opt-out half of the ADR-160 D3 polarity inversion."""
    result = PhaseWorkflowResult(
        ok=True, phase_results=[PhaseResult(name="execution", ok=True)]
    )
    worker = _fake_worker(result)

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ) as worker_cls:
        await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
            write=True,
            legacy_direct_write=True,
        )

    _, kwargs = worker_cls.call_args
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
# write=True with no legacy_direct_write is the fail-closed default (polarity
# inversion) -- these two tests exercise the message-construction branch,
# which the inversion did not change; only how create_proposal_only is
# derived changed (see test_fail_closed_default_write_true_reaches_worker_as_
# create_proposal_only above).


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
        )

    assert ok is False
    assert "could not be converted to a Proposal" in message
    assert "does not execute the planned tasks" in message
