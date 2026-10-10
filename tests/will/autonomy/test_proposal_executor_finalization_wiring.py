"""Fault-injection tests for ProposalExecutor.execute's finalization wiring
(ADR-148, #763/#773 T5.2).

The existing test_proposal_commit_outcome.py and test_proposal_state_
transitions.py test the pure classification functions (CommitOutcome,
transition predicates) in isolation. Neither drives ProposalExecutor.execute
end-to-end, so neither proves the WIRING: that a CommitOutcome.FAILED
actually triggers rollback_proposal + mark_failed, or that a post-
mark_finalizing consequence-recording failure actually leaves the proposal
in finalizing rather than reaching mark_completed. These tests close that
gap directly against the real execute() method, with every collaborator
(DB session, repository, action executor, git/pipeline functions, state
manager) mocked.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_execution_pipeline import CommitOutcome
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_state_manager import ProposalStatus


def _make_proposal(**overrides: object) -> MagicMock:
    proposal = MagicMock()
    proposal.proposal_id = "pid-exec-1"
    proposal.status = ProposalStatus.APPROVED
    proposal.actions = []  # empty action list -> loop body never runs, all_ok stays True
    proposal.goal = "test goal"
    proposal.constitutional_constraints = {"finding_ids": []}
    proposal.scope = MagicMock(policies=[])
    for key, value in overrides.items():
        setattr(proposal, key, value)
    return proposal


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _make_executor(proposal: MagicMock) -> tuple[ProposalExecutor, MagicMock]:
    """Bypass ProposalExecutor.__init__ (constructs a real ActionExecutor)
    — set minimal attributes and a mocked action_executor by hand."""
    executor = object.__new__(ProposalExecutor)
    executor.core_context = MagicMock()
    executor.action_executor = AsyncMock()
    executor.action_executor.execute = AsyncMock(
        return_value=MagicMock(ok=True, data={})
    )

    repo_instance = AsyncMock()
    repo_instance.get = AsyncMock(return_value=proposal)

    session = AsyncMock()
    return executor, session, repo_instance


async def test_commit_failure_triggers_rollback_and_mark_failed() -> None:
    """CommitOutcome.FAILED must actually route through rollback_proposal +
    mark_failed — not just be classified correctly by the pure function."""
    proposal = _make_proposal()
    executor, session, repo_instance = _make_executor(proposal)

    mark_failed_mock = AsyncMock()
    mark_finalizing_mock = AsyncMock()
    mark_completed_mock = AsyncMock()
    rollback_mock = MagicMock(return_value=None)  # rollback verified

    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager"
        ) as state_manager_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.FAILED),
        ),
        patch("will.autonomy.proposal_executor.rollback_proposal", rollback_mock),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(),
        ) as record_consequence_mock,
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(),
        ),
    ):
        state_manager_instance = state_manager_cls.return_value
        state_manager_instance.mark_failed = mark_failed_mock
        state_manager_instance.mark_finalizing = mark_finalizing_mock
        state_manager_instance.mark_completed = mark_completed_mock

        result = await executor.execute(
            "pid-exec-1", claimed_by=MagicMock(), write=True
        )

    assert result["ok"] is False
    assert result["lifecycle_status"] == "failed"
    rollback_mock.assert_called_once()
    mark_failed_mock.assert_awaited_once()
    assert mark_failed_mock.await_args.args[0] == "pid-exec-1"
    mark_finalizing_mock.assert_not_awaited()
    mark_completed_mock.assert_not_awaited()
    record_consequence_mock.assert_not_awaited()


async def test_consequence_failure_after_finalizing_never_reaches_completed() -> None:
    """record_consequence returning False after mark_finalizing succeeded
    must leave the proposal in finalizing — mark_completed must not be
    called. The stuck-finalizing reaper (ADR-148 D4) picks it up later.

    #812: `ok` stays True here — its contract (no action/commit failure)
    is genuinely unchanged and still correct for a synchronous caller. The
    load-bearing assertion for "did this reach the durable proof state" is
    lifecycle_status, which callers that need ADR-148's guarantee (e.g.
    ProposalConsumerWorker) must check instead of `ok` — see
    test_proposal_consumer_worker_lifecycle_gating.py for that side."""
    proposal = _make_proposal()
    executor, session, repo_instance = _make_executor(proposal)

    mark_failed_mock = AsyncMock()
    mark_finalizing_mock = AsyncMock()
    mark_completed_mock = AsyncMock()

    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager"
        ) as state_manager_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.COMMITTED),
        ),
        patch(
            "will.autonomy.proposal_executor.compute_changed_files",
            AsyncMock(return_value=[]),
        ),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(return_value=False),
        ) as record_consequence_mock,
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(return_value=True),
        ) as resolve_findings_mock,
    ):
        state_manager_instance = state_manager_cls.return_value
        state_manager_instance.mark_failed = mark_failed_mock
        state_manager_instance.mark_finalizing = mark_finalizing_mock
        state_manager_instance.mark_completed = mark_completed_mock

        result = await executor.execute(
            "pid-exec-1", claimed_by=MagicMock(), write=True
        )

    assert result["ok"] is True
    assert result["lifecycle_status"] == "finalizing"
    mark_finalizing_mock.assert_awaited_once()
    record_consequence_mock.assert_awaited_once()
    resolve_findings_mock.assert_awaited_once()
    mark_completed_mock.assert_not_awaited()
    mark_failed_mock.assert_not_awaited()


async def test_commit_and_consequence_success_reaches_completed() -> None:
    """Positive control: commit succeeds, consequence + findings resolve ok
    -> mark_completed IS called. Confirms the two fault-injection tests
    above are asserting against real branching, not a mock that always
    no-ops."""
    proposal = _make_proposal()
    executor, session, repo_instance = _make_executor(proposal)

    mark_failed_mock = AsyncMock()
    mark_finalizing_mock = AsyncMock()
    mark_completed_mock = AsyncMock()

    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager"
        ) as state_manager_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.COMMITTED),
        ),
        patch(
            "will.autonomy.proposal_executor.compute_changed_files",
            AsyncMock(return_value=["a.py"]),
        ),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(return_value=True),
        ),
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(return_value=True),
        ),
    ):
        state_manager_instance = state_manager_cls.return_value
        state_manager_instance.mark_failed = mark_failed_mock
        state_manager_instance.mark_finalizing = mark_finalizing_mock
        state_manager_instance.mark_completed = mark_completed_mock

        result = await executor.execute(
            "pid-exec-1", claimed_by=MagicMock(), write=True
        )

    assert result["ok"] is True
    assert result["lifecycle_status"] == "completed"
    mark_finalizing_mock.assert_awaited_once()
    mark_completed_mock.assert_awaited_once_with("pid-exec-1")
    mark_failed_mock.assert_not_awaited()


async def test_incomplete_rollback_is_part_of_the_failure_reason() -> None:
    """#871: a rollback that could not restore the production set is
    recorded in the proposal's failure reason, not only logged."""
    proposal = _make_proposal()
    executor, session, repo_instance = _make_executor(proposal)
    mark_failed_mock = AsyncMock()

    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager"
        ) as state_manager_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.FAILED),
        ),
        patch(
            "will.autonomy.proposal_executor.rollback_proposal",
            MagicMock(return_value="1 production path(s) still differ: a.py"),
        ),
        patch("will.autonomy.proposal_executor.record_consequence", AsyncMock()),
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(),
        ),
    ):
        state_manager_cls.return_value.mark_failed = mark_failed_mock
        result = await executor.execute(
            "pid-exec-1", claimed_by=MagicMock(), write=True
        )

    assert result["lifecycle_status"] == "failed"
    reason = mark_failed_mock.await_args.kwargs["reason"]
    assert reason.startswith("ADR-148 D3: git commit failed")
    assert "ROLLBACK INCOMPLETE: 1 production path(s) still differ: a.py" in reason


async def test_actions_execute_under_the_proposals_approval_authority() -> None:
    """#903: the executor's envelope check needs to know how the proposal
    was approved; ProposalExecutor dispatches each action inside
    approval_scope(proposal.approval_authority), and resets it after."""
    from shared.governance_token import current_approval_authority

    action = MagicMock(ref_id="fix.format", ref_kind="action", order=0, parameters={})
    proposal = _make_proposal(
        actions=[action],
        approval_authority="risk_classification.safe_auto_approval",
    )
    executor, session, repo_instance = _make_executor(proposal)
    seen: list[str | None] = []

    async def _execute(*_args: object, **kwargs: object) -> MagicMock:
        if kwargs.get("action_id") == "fix.format":  # not the claim call
            seen.append(current_approval_authority())
        return MagicMock(ok=True, data={})

    executor.action_executor.execute = AsyncMock(side_effect=_execute)

    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager",
            MagicMock(return_value=AsyncMock()),
        ),
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        # The commit-failure branch (as in the sibling tests): fully stubbed,
        # so no completion-path collaborator can reach the database. Only
        # the approval scope during dispatch is under test here.
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.FAILED),
        ),
        patch(
            "will.autonomy.proposal_executor.rollback_proposal",
            MagicMock(return_value=None),
        ),
        patch("will.autonomy.proposal_executor.record_consequence", AsyncMock()),
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(),
        ),
    ):
        await executor.execute("pid-exec-1", claimed_by=MagicMock(), write=True)

    assert seen == ["risk_classification.safe_auto_approval"]
    assert current_approval_authority() is None


async def _commit_kwargs(proposal: MagicMock) -> dict:
    executor, session, repo_instance = _make_executor(proposal)
    commit = MagicMock(return_value=CommitOutcome.COMMITTED)
    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalStateManager",
            MagicMock(return_value=AsyncMock()),
        ),
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch("will.autonomy.proposal_executor.commit_proposal_changes", commit),
        patch(
            "will.autonomy.proposal_executor.compute_changed_files",
            AsyncMock(return_value=["a.py"]),
        ),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(return_value=True),
        ),
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(return_value=True),
        ),
    ):
        await executor.execute("pid-exec-1", claimed_by=MagicMock(), write=True)
    return commit.call_args.kwargs


# ID: d19b53b6-3fa4-4195-a682-628698bc8883
async def test_commit_receives_the_proposals_producer() -> None:
    """ADR-168 Amendment 2026-10-10 A6: the producer recorded on the proposal
    becomes the commit's author; a pre-provenance proposal passes None."""
    from types import SimpleNamespace

    with_producer = _make_proposal(
        provenance=SimpleNamespace(producer="claude-session:core-darek")
    )
    assert (await _commit_kwargs(with_producer))["producer"] == (
        "claude-session:core-darek"
    )
    assert (await _commit_kwargs(_make_proposal(provenance=None)))["producer"] is None
