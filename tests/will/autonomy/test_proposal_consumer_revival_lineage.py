# tests/will/autonomy/test_proposal_consumer_revival_lineage.py
"""Unit tests: revival lineage routing (governor decision, 2026-08-23).

revive_and_report must route an assisted-lane proposal's execution
failure to revive_delegated_findings_for_failed_proposal (indeterminate+
human, no remediation cap) and never touch the autonomous
revive_findings_for_failed_proposal / remediation-cap-observation path —
and vice versa for autonomous proposals. _is_assisted_lane_proposal is the
sole routing signal; it is fail-closed to False (autonomous) on any error.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_consumer_revival import (
    _is_assisted_lane_proposal,
    revive_and_report,
)


_PROPOSAL_ID = "prop-lineage-0001"


def _make_worker() -> MagicMock:
    worker = MagicMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()
    return worker


def _patch_repo_get(proposal):
    """Patch ProposalRepository so .get(proposal_id) returns *proposal*
    (or raises, if *proposal* is an Exception instance)."""
    repo_instance = MagicMock()
    if isinstance(proposal, Exception):
        repo_instance.get = AsyncMock(side_effect=proposal)
    else:
        repo_instance.get = AsyncMock(return_value=proposal)
    repo_cls = MagicMock(return_value=repo_instance)

    session = AsyncMock()

    @asynccontextmanager
    async def _session():
        yield session

    return (
        patch("will.autonomy.proposal_repository.ProposalRepository", repo_cls),
        patch(
            "body.services.service_registry.service_registry.session",
            _session,
        ),
    )


def _proposal_with(assisted_lane: bool | None) -> MagicMock:
    proposal = MagicMock()
    proposal.constitutional_constraints = (
        {} if assisted_lane is None else {"assisted_lane": assisted_lane}
    )
    return proposal


# --- _is_assisted_lane_proposal -----------------------------------------


async def test_is_assisted_lane_proposal_true_when_flag_set():
    p_repo, p_session = _patch_repo_get(_proposal_with(True))
    with p_repo, p_session:
        assert await _is_assisted_lane_proposal(_PROPOSAL_ID) is True


async def test_is_assisted_lane_proposal_false_when_flag_absent():
    p_repo, p_session = _patch_repo_get(_proposal_with(None))
    with p_repo, p_session:
        assert await _is_assisted_lane_proposal(_PROPOSAL_ID) is False


async def test_is_assisted_lane_proposal_false_when_flag_explicitly_false():
    p_repo, p_session = _patch_repo_get(_proposal_with(False))
    with p_repo, p_session:
        assert await _is_assisted_lane_proposal(_PROPOSAL_ID) is False


async def test_is_assisted_lane_proposal_false_when_proposal_missing():
    p_repo, p_session = _patch_repo_get(None)
    with p_repo, p_session:
        assert await _is_assisted_lane_proposal(_PROPOSAL_ID) is False


async def test_is_assisted_lane_proposal_fail_closed_on_lookup_error():
    """A lookup hiccup degrades to the autonomous default rather than
    raising into the revival contract — the pre-existing fail-soft
    posture, extended to the new lineage check."""
    p_repo, p_session = _patch_repo_get(RuntimeError("db unavailable"))
    with p_repo, p_session:
        assert await _is_assisted_lane_proposal(_PROPOSAL_ID) is False


# --- revive_and_report routing ------------------------------------------


async def test_assisted_lane_execution_failure_routes_to_delegated_revival():
    """4. Assisted-lane execution failure never calls the autonomous
    remediation-cap path — no autonomous revival call, no cap observation.
    3. A revival report is still posted (durable failure evidence)."""
    worker = _make_worker()
    bb_service = MagicMock()
    bb_service.revive_delegated_findings_for_failed_proposal = AsyncMock(
        return_value={
            "proposal_id": _PROPOSAL_ID,
            "failure_reason": "assisted.apply_diff failed",
            "revived_count": 1,
            "revived_finding_ids": ["f-1"],
            "revived_subjects": ["purity.no_orphan_files::src/x.py"],
        }
    )
    bb_service.revive_findings_for_failed_proposal = AsyncMock()
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)

    with (
        patch(
            "will.autonomy.proposal_consumer_revival._is_assisted_lane_proposal",
            AsyncMock(return_value=True),
        ),
        patch("body.services.service_registry.service_registry", registry),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "assisted.apply_diff failed")

    bb_service.revive_delegated_findings_for_failed_proposal.assert_awaited_once_with(
        proposal_id=_PROPOSAL_ID, failure_reason="assisted.apply_diff failed"
    )
    bb_service.revive_findings_for_failed_proposal.assert_not_awaited()
    worker.post_observation.assert_not_awaited()  # no remediation-cap path
    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["subject"] == f"proposal.failure.revival::{_PROPOSAL_ID}"
    assert report_kwargs["payload"]["revived_count"] == 1


async def test_autonomous_proposal_execution_failure_routes_to_autonomous_revival():
    """5. Non-assisted-lane proposals are unaffected: the autonomous path
    (with its remediation-cap rail) still runs, and the assisted-lane
    method is never called."""
    worker = _make_worker()
    bb_service = MagicMock()
    bb_service.revive_findings_for_failed_proposal = AsyncMock(
        return_value={
            "proposal_id": _PROPOSAL_ID,
            "failure_reason": "autonomous action failed",
            "revived_count": 1,
            "revived_finding_ids": ["f-2"],
            "revived_subjects": ["audit.violation::purity.no_orphan_files::src/y.py"],
            "abandoned_count": 0,
            "abandoned_finding_ids": [],
            "abandoned_subjects": [],
        }
    )
    bb_service.revive_delegated_findings_for_failed_proposal = AsyncMock()
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)

    with (
        patch(
            "will.autonomy.proposal_consumer_revival._is_assisted_lane_proposal",
            AsyncMock(return_value=False),
        ),
        patch("body.services.service_registry.service_registry", registry),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=3)),
        ),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "autonomous action failed")

    bb_service.revive_findings_for_failed_proposal.assert_awaited_once_with(
        proposal_id=_PROPOSAL_ID,
        failure_reason="autonomous action failed",
        remediation_cap_n=3,
    )
    bb_service.revive_delegated_findings_for_failed_proposal.assert_not_awaited()
    worker.post_report.assert_awaited_once()


async def test_assisted_lane_revival_with_zero_findings_posts_no_report():
    """A zero-revival outcome is legitimate and silent, same as the
    autonomous path."""
    worker = _make_worker()
    bb_service = MagicMock()
    bb_service.revive_delegated_findings_for_failed_proposal = AsyncMock(
        return_value=None
    )
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)

    with (
        patch(
            "will.autonomy.proposal_consumer_revival._is_assisted_lane_proposal",
            AsyncMock(return_value=True),
        ),
        patch("body.services.service_registry.service_registry", registry),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "nothing to revive")

    worker.post_report.assert_not_awaited()
    worker.post_observation.assert_not_awaited()
