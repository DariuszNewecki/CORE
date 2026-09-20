# tests/will/autonomy/test_noop_completion_revival.py
"""A NOTHING_TO_COMMIT completion revives its deferred findings instead of
resolving them (ADR-104 D9 applied to the no-op loop, #901).

Before this change a ``fix.*`` proposal that ran clean and changed nothing
still completed, marked every deferred finding ``resolved by <proposal>``
and recorded them as ``findings_resolved`` — a false claim the sensor
undid five minutes later by re-posting the same violation, which minted the
next no-op proposal with every rail reset (809 such proposals in the week
before the fix). Three layers are pinned here:

- the pipeline helper ``revive_deferred_findings_for_noop`` calls the
  capped revival predicate with the governed cap and returns the revival
  for the Worker to report (it never posts itself —
  ``architecture.blackboard.worker_only_inserts``);
- ``ProposalExecutor.execute`` routes a NOTHING_TO_COMMIT outcome to that
  helper, not to ``resolve_deferred_findings``, records no
  ``findings_resolved`` for it, still reaches COMPLETED (ADR-148 D3: a
  legitimately-empty production set is not a failure), and surfaces
  ``commit_outcome`` + ``findings_revival`` in its result;
- ``report_revival`` names the report by the caller's subject family, so a
  no-op completion is reported as ``proposal.noop.revival``, not as a
  failure.

Every collaborator is mocked; no DB, no blackboard.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_consumer_revival import report_revival
from will.autonomy.proposal_execution_pipeline import (
    NOOP_COMPLETION_REASON,
    CommitOutcome,
    revive_deferred_findings_for_noop,
)
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_state_manager import ProposalStatus


# ---------------------------------------------------------------------------
# Pipeline helper
# ---------------------------------------------------------------------------


# ID: ae665fba-3199-42fb-84e7-fa531630d354
async def test_helper_revives_with_governed_cap_and_returns_revival() -> None:
    revival = {
        "proposal_id": "pid-noop",
        "failure_reason": NOOP_COMPLETION_REASON,
        "revived_count": 1,
        "revived_finding_ids": ["f-1"],
        "revived_subjects": ["python::rule::a.py"],
        "abandoned_count": 0,
        "abandoned_finding_ids": [],
        "abandoned_subjects": [],
    }
    bb = MagicMock()
    bb.revive_findings_for_failed_proposal = AsyncMock(return_value=revival)
    config = MagicMock()
    config.blackboard.remediation_cap_n = 3

    with (
        patch(
            "will.autonomy.proposal_execution_pipeline.service_registry"
            ".get_blackboard_service",
            AsyncMock(return_value=bb),
        ),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=config,
        ),
    ):
        adjudicated, got = await revive_deferred_findings_for_noop("pid-noop")

    assert adjudicated is True
    assert got is revival
    bb.revive_findings_for_failed_proposal.assert_awaited_once_with(
        proposal_id="pid-noop",
        failure_reason=NOOP_COMPLETION_REASON,
        remediation_cap_n=3,
    )


# ID: 83ca19c5-2f08-450a-865e-494ca29fb277
async def test_helper_reports_not_adjudicated_when_the_service_raises() -> None:
    """A revival outage must leave the proposal FINALIZING (recoverable by
    the reaper), never COMPLETED with findings still deferred to it."""
    bb = MagicMock()
    bb.revive_findings_for_failed_proposal = AsyncMock(
        side_effect=RuntimeError("db down")
    )
    with patch(
        "will.autonomy.proposal_execution_pipeline.service_registry"
        ".get_blackboard_service",
        AsyncMock(return_value=bb),
    ):
        adjudicated, got = await revive_deferred_findings_for_noop("pid-noop")

    assert adjudicated is False
    assert got is None


# ---------------------------------------------------------------------------
# Executor wiring
# ---------------------------------------------------------------------------


def _make_proposal() -> MagicMock:
    proposal = MagicMock()
    proposal.proposal_id = "pid-noop"
    proposal.status = ProposalStatus.APPROVED
    proposal.actions = []
    proposal.goal = "Autonomous remediation: fix.logging (1 violation(s))"
    proposal.constitutional_constraints = {"finding_ids": ["f-1"]}
    proposal.scope = MagicMock(policies=["architecture.channels"])
    return proposal


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _make_executor() -> tuple[ProposalExecutor, MagicMock, MagicMock]:
    executor = object.__new__(ProposalExecutor)
    executor.core_context = MagicMock()
    executor.action_executor = AsyncMock()
    repo_instance = AsyncMock()
    repo_instance.get = AsyncMock(return_value=_make_proposal())
    return executor, AsyncMock(), repo_instance


async def _execute_with(commit_outcome: CommitOutcome) -> tuple[dict, dict]:
    executor, session, repo_instance = _make_executor()
    revival = {"proposal_id": "pid-noop", "revived_count": 1}
    mocks = {
        "record": AsyncMock(return_value=True),
        "resolve": AsyncMock(return_value=True),
        "revive": AsyncMock(return_value=(True, revival)),
        "mark_completed": AsyncMock(),
        "mark_failed": AsyncMock(),
    }
    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch("will.autonomy.proposal_executor.ProposalStateManager") as sm_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=commit_outcome),
        ),
        patch(
            "will.autonomy.proposal_executor.compute_changed_files",
            AsyncMock(return_value=[]),
        ),
        patch("will.autonomy.proposal_executor.record_consequence", mocks["record"]),
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            mocks["resolve"],
        ),
        patch(
            "will.autonomy.proposal_executor.revive_deferred_findings_for_noop",
            mocks["revive"],
        ),
    ):
        sm = sm_cls.return_value
        sm.mark_finalizing = AsyncMock()
        sm.mark_completed = mocks["mark_completed"]
        sm.mark_failed = mocks["mark_failed"]
        result = await executor.execute("pid-noop", claimed_by=MagicMock(), write=True)
    return result, mocks


# ID: 07c686de-920c-478a-a19f-ce3af9ff6cb1
async def test_nothing_to_commit_revives_instead_of_resolving() -> None:
    result, mocks = await _execute_with(CommitOutcome.NOTHING_TO_COMMIT)

    mocks["revive"].assert_awaited_once_with("pid-noop")
    mocks["resolve"].assert_not_awaited()
    # Nothing was resolved, so the consequence record must not claim it.
    assert mocks["record"].await_args.kwargs["finding_ids"] == []
    # ADR-148 D3: a legitimately-empty production set still completes.
    mocks["mark_completed"].assert_awaited_once_with("pid-noop")
    mocks["mark_failed"].assert_not_awaited()
    assert result["lifecycle_status"] == "completed"
    assert result["commit_outcome"] == "nothing_to_commit"
    assert result["findings_revival"] == {"proposal_id": "pid-noop", "revived_count": 1}


# ID: 46c4102b-f642-4efc-8bd3-b5f480e7ca7b
async def test_real_commit_still_resolves_and_records_findings() -> None:
    """Positive control: the branch is on the commit outcome, not always-on."""
    result, mocks = await _execute_with(CommitOutcome.COMMITTED)

    mocks["resolve"].assert_awaited_once_with("pid-noop")
    mocks["revive"].assert_not_awaited()
    assert mocks["record"].await_args.kwargs["finding_ids"] == ["f-1"]
    assert result["lifecycle_status"] == "completed"
    assert result["commit_outcome"] == "committed"
    assert result["findings_revival"] is None


# ID: 3408d334-8139-474a-b168-c1b64d55b841
async def test_nothing_to_commit_with_revival_outage_stays_finalizing() -> None:
    executor, session, repo_instance = _make_executor()
    mark_completed = AsyncMock()
    with (
        patch(
            "will.autonomy.proposal_executor.service_registry.session",
            MagicMock(return_value=_session_ctx(session)),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo_instance),
        ),
        patch("will.autonomy.proposal_executor.ProposalStateManager") as sm_cls,
        patch(
            "will.autonomy.proposal_executor.capture_git_sha",
            MagicMock(return_value="deadbeef"),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes",
            MagicMock(return_value=CommitOutcome.NOTHING_TO_COMMIT),
        ),
        patch(
            "will.autonomy.proposal_executor.compute_changed_files",
            AsyncMock(return_value=[]),
        ),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(return_value=True),
        ),
        patch(
            "will.autonomy.proposal_executor.revive_deferred_findings_for_noop",
            AsyncMock(return_value=(False, None)),
        ),
    ):
        sm = sm_cls.return_value
        sm.mark_finalizing = AsyncMock()
        sm.mark_completed = mark_completed
        sm.mark_failed = AsyncMock()
        result = await executor.execute("pid-noop", claimed_by=MagicMock(), write=True)

    mark_completed.assert_not_awaited()
    assert result["lifecycle_status"] == "finalizing"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


# ID: d4b6c9b8-b4fd-4e8e-8874-79c7de298dbc
async def test_report_revival_uses_the_callers_subject_family() -> None:
    worker = MagicMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    revival = {
        "proposal_id": "pid-noop",
        "failure_reason": NOOP_COMPLETION_REASON,
        "revived_count": 1,
        "revived_subjects": ["python::rule::a.py"],
        "abandoned_finding_ids": ["f-2"],
        "abandoned_subjects": ["python::rule::b.py"],
    }
    config = MagicMock()
    config.blackboard.remediation_cap_n = 3
    with patch(
        "shared.infrastructure.intent.operational_config.load_operational_config",
        return_value=config,
    ):
        await report_revival(
            worker, "pid-noop", revival, report_subject_family="proposal.noop.revival"
        )

    # One terminal cap observation per abandoned finding (ADR-104 D9 / D4).
    worker.post_observation.assert_awaited_once()
    obs = worker.post_observation.await_args.kwargs
    assert obs["subject"] == "blackboard.remediation_cap_reached::python::rule::b.py"
    assert obs["status"] == "abandoned"
    assert obs["payload"]["remediation_cap_n"] == 3
    # The revival report is named as a no-op, not a failure.
    worker.post_report.assert_awaited_once()
    assert (
        worker.post_report.await_args.kwargs["subject"]
        == "proposal.noop.revival::pid-noop"
    )


# ID: c0e48a3f-d07f-467d-86c2-19eed9015d63
async def test_report_revival_default_family_is_unchanged_for_failures() -> None:
    worker = MagicMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    await report_revival(
        worker,
        "pid-fail",
        {
            "proposal_id": "pid-fail",
            "failure_reason": "boom",
            "revived_count": 1,
            "revived_subjects": ["s"],
        },
    )
    assert (
        worker.post_report.await_args.kwargs["subject"]
        == "proposal.failure.revival::pid-fail"
    )
