# tests/will/autonomy/test_proposal_consumer_revival_lineage.py
"""Unit tests: revival lineage routing (ADR-154 D3, governor decision 2026-08-23).

revive_and_report must route an assisted-lane proposal's execution failure
to revive_delegated_findings_for_failed_proposal (indeterminate+human, no
remediation cap) and never touch the autonomous
revive_findings_for_failed_proposal / remediation-cap-observation path — and
a ceremony proposal's execution failure must route to the SAME autonomous
target as a plain autonomous proposal (ADR-154 D3: ceremony findings stay
resolution_mechanism='reaudit' while deferred, so the generic ADR-038
circuit-breaker path applies). _proposal_revival_lineage is the sole routing
signal (three-way: assisted_lane / ceremony / autonomous); it is fail-closed
to "autonomous" on any error.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_consumer_revival import (
    _proposal_revival_lineage,
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


def _proposal_with(constraints: dict | None) -> MagicMock:
    proposal = MagicMock()
    proposal.constitutional_constraints = constraints or {}
    return proposal


# --- _proposal_revival_lineage -------------------------------------------


async def test_lineage_assisted_lane_when_flag_set():
    p_repo, p_session = _patch_repo_get(_proposal_with({"assisted_lane": True}))
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "assisted_lane"


async def test_lineage_ceremony_when_origin_marker_set():
    p_repo, p_session = _patch_repo_get(_proposal_with({"proposal_origin": "ceremony"}))
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "ceremony"


async def test_lineage_autonomous_when_no_markers():
    p_repo, p_session = _patch_repo_get(_proposal_with(None))
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "autonomous"


async def test_lineage_autonomous_when_assisted_lane_explicitly_false():
    p_repo, p_session = _patch_repo_get(_proposal_with({"assisted_lane": False}))
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "autonomous"


async def test_lineage_autonomous_when_proposal_missing():
    p_repo, p_session = _patch_repo_get(None)
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "autonomous"


async def test_lineage_fail_closed_to_autonomous_on_lookup_error():
    """A lookup hiccup degrades to the autonomous default rather than
    raising into the revival contract — the pre-existing fail-soft
    posture, extended to the three-way lineage check."""
    p_repo, p_session = _patch_repo_get(RuntimeError("db unavailable"))
    with p_repo, p_session:
        assert await _proposal_revival_lineage(_PROPOSAL_ID) == "autonomous"


# --- revive_and_report routing --------------------------------------------


async def test_assisted_lane_execution_failure_routes_to_delegated_revival():
    """Assisted-lane execution failure never calls the autonomous
    remediation-cap path — no autonomous revival call, no cap observation.
    A revival report is still posted (durable failure evidence)."""
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
            "will.autonomy.proposal_consumer_revival._proposal_revival_lineage",
            AsyncMock(return_value="assisted_lane"),
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
    """Non-assisted-lane, non-ceremony proposals are unaffected: the
    autonomous path (with its remediation-cap rail) still runs, and the
    assisted-lane method is never called."""
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
            "will.autonomy.proposal_consumer_revival._proposal_revival_lineage",
            AsyncMock(return_value="autonomous"),
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


async def test_ceremony_execution_failure_routes_to_autonomous_revival_not_assisted():
    """ADR-154 D3, the exact trap the governor flagged: a ceremony
    proposal's EXECUTION failure must route to the same autonomous/ADR-038
    target as a plain autonomous proposal (revive_findings_for_failed_proposal,
    with the remediation cap) — NEVER to the assisted-lane
    indeterminate+human path. Ceremony findings stay resolution_mechanism=
    'reaudit' while deferred, which is exactly what the autonomous
    predicate requires."""
    worker = _make_worker()
    bb_service = MagicMock()
    bb_service.revive_findings_for_failed_proposal = AsyncMock(
        return_value={
            "proposal_id": _PROPOSAL_ID,
            "failure_reason": "ceremony execution failed",
            "revived_count": 1,
            "revived_finding_ids": ["f-3"],
            "revived_subjects": [
                "audit.violation::modularity.class_too_large::src/z.py"
            ],
            "abandoned_count": 0,
            "abandoned_finding_ids": [],
            "abandoned_subjects": [],
        }
    )
    bb_service.revive_delegated_findings_for_failed_proposal = AsyncMock()
    bb_service.revive_ceremony_findings_for_rejected_proposal = AsyncMock()
    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)

    with (
        patch(
            "will.autonomy.proposal_consumer_revival._proposal_revival_lineage",
            AsyncMock(return_value="ceremony"),
        ),
        patch("body.services.service_registry.service_registry", registry),
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=3)),
        ),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "ceremony execution failed")

    bb_service.revive_findings_for_failed_proposal.assert_awaited_once_with(
        proposal_id=_PROPOSAL_ID,
        failure_reason="ceremony execution failed",
        remediation_cap_n=3,
    )
    bb_service.revive_delegated_findings_for_failed_proposal.assert_not_awaited()
    bb_service.revive_ceremony_findings_for_rejected_proposal.assert_not_awaited()


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
            "will.autonomy.proposal_consumer_revival._proposal_revival_lineage",
            AsyncMock(return_value="assisted_lane"),
        ),
        patch("body.services.service_registry.service_registry", registry),
    ):
        await revive_and_report(worker, _PROPOSAL_ID, "nothing to revive")

    worker.post_report.assert_not_awaited()
    worker.post_observation.assert_not_awaited()
