# tests/will/autonomy/test_lane_service.py

"""Unit tests for LaneService — Assisted Remediation Lane (ADR-109 #652).

LaneService is the Will-layer facade the lane API routes through. It owns no
state and no session; it delegates to the BlackboardService obtained from the
service_registry. The test stubs that registry call and asserts the limit is
forwarded and the rows passed straight back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.proposal_submission_service import ProposalSubmissionError
from shared.infrastructure.intent.errors import GovernanceError
from shared.models.validated_remediation_candidate import (
    _CONSTRUCTOR_TOKEN,
    CandidateConstructionError,
    ValidatedRemediationCandidate,
)
from will.autonomy.lane_service import LaneProposeError, LaneService


def _candidate(**overrides) -> ValidatedRemediationCandidate:
    """A fully-formed candidate for tests that don't care about every field.

    LaneService never constructs a candidate itself in production — it only
    ever receives one back from build_validated_candidate (mocked here) — so
    reaching for the real construction token in a test fixture is legitimate:
    it exercises the same privileged path the real service uses, rather than
    working around it.
    """
    defaults = dict(
        candidate_id="cand-1",
        patch="--- a/src/x.py\n+++ b/src/x.py\n",
        patch_digest="deadbeef",
        production_set=["src/x.py", "src/base.py"],
        validated_base_sha="base-sha-1",
        validation_checks=["assisted.validate_diff"],
        validation_results={"assisted.validate_diff": True},
        finding_ids=["f-1"],
        rule_ids=["modularity.class_too_large"],
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    defaults.update(overrides)
    return ValidatedRemediationCandidate(
        **defaults, _construction_token=_CONSTRUCTOR_TOKEN
    )


async def test_list_delegated_findings_delegates_to_blackboard():
    """list_delegated_findings forwards the limit to
    BlackboardService.fetch_delegated_findings and returns its rows verbatim."""
    rows = [{"id": "f-1", "subject": "s", "payload": {}, "created_at": None}]

    bb_service = AsyncMock()
    bb_service.fetch_delegated_findings = AsyncMock(return_value=rows)

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        out = await LaneService().list_delegated_findings(limit=10)

    assert out == rows
    bb_service.fetch_delegated_findings.assert_awaited_once_with(limit=10)


async def test_get_delegated_finding_delegates_to_blackboard():
    """get_delegated_finding forwards the id to fetch_delegated_finding."""
    finding = {"id": "f-9", "subject": "s", "payload": {}, "created_at": None}
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(return_value=finding)

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        out = await LaneService().get_delegated_finding("f-9")

    assert out == finding
    bb_service.fetch_delegated_finding.assert_awaited_once_with("f-9")


async def test_propose_validated_diff_creates_proposal_and_defers():
    """The happy path constructs the frozen candidate via the Body-owned
    trusted validation service, builds a human-gated, validation-gated,
    assisted-lane proposal that runs assisted.apply_diff with the patch and
    the candidate's validated_base_sha/patch_digest (ADR-154 D2), then hands
    the whole proposal + finding_ids to the atomic submission service
    (ADR-154 D3b) — proposal persistence and finding deferral are no longer
    two separate calls/sessions."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-1",
            "subject": "modularity.class_too_large::src/x.py",
            "payload": {"rule": "modularity.class_too_large"},
            "created_at": None,
        }
    )
    candidate = _candidate()
    build_candidate = AsyncMock(return_value=candidate)
    submit = AsyncMock(return_value="prop-abc")

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch("will.autonomy.lane_service.build_validated_candidate", build_candidate),
        patch("will.autonomy.lane_service.submit_assisted_lane_proposal", submit),
    ):
        proposal_id, production_set = await LaneService().propose_validated_diff(
            finding_id="f-1",
            patch="--- a/src/x.py\n+++ b/src/x.py\n",
            validation_run_id="run-1",
        )

    assert proposal_id == "prop-abc"
    assert production_set == candidate.production_set

    build_candidate.assert_awaited_once_with(
        finding_ids=["f-1"],
        rule_ids=["modularity.class_too_large"],
        patch="--- a/src/x.py\n+++ b/src/x.py\n",
        validation_run_id="run-1",
    )

    # The proposal handed to the atomic submission service carries the
    # lane's mandatory shape, sourced from the candidate's own recorded
    # verdict — never asserted — and finding_ids travels as a set (D3b).
    (proposal,), kwargs = submit.call_args
    assert kwargs["finding_ids"] == ["f-1"]
    assert proposal.approval_required is True  # ADR-109 D3 — mandatory
    assert proposal.validation_checks == candidate.validation_checks
    assert proposal.validation_results == candidate.validation_results
    assert proposal.scope.files == candidate.production_set
    assert proposal.constitutional_constraints["assisted_lane"] is True
    assert proposal.constitutional_constraints["finding_ids"] == ["f-1"]
    assert proposal.constitutional_constraints["rules"] == [
        "modularity.class_too_large"
    ]
    assert proposal.constitutional_constraints["candidate_id"] == "cand-1"
    assert proposal.constitutional_constraints["validated_base_sha"] == "base-sha-1"
    # The remaining D2 evidence gap: the candidate's own created_at must be
    # durably carried into the proposal too (no separate candidate table).
    assert (
        proposal.constitutional_constraints["candidate_created_at"]
        == candidate.created_at.isoformat()
    )
    assert len(proposal.actions) == 1
    action = proposal.actions[0]
    assert action.action_id == "assisted.apply_diff"
    assert action.parameters["patch"] == candidate.patch
    assert action.parameters["patch_digest"] == "deadbeef"
    assert action.parameters["validated_base_sha"] == "base-sha-1"


async def test_propose_raises_when_finding_not_live():
    """A finding that is not a live delegated lane item (None) raises
    LaneProposeError before candidate construction or atomic submission."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(return_value=None)
    build_candidate = AsyncMock()
    submit = AsyncMock()

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch("will.autonomy.lane_service.build_validated_candidate", build_candidate),
        patch("will.autonomy.lane_service.submit_assisted_lane_proposal", submit),
    ):
        with pytest.raises(LaneProposeError):
            await LaneService().propose_validated_diff(
                finding_id="missing",
                patch="x",
                validation_run_id="run-1",
            )

    build_candidate.assert_not_awaited()
    submit.assert_not_awaited()


async def test_propose_propagates_candidate_construction_error():
    """A validation run that fails ADR-154 D2's preconditions (unknown run,
    patch mismatch, missing base SHA, ...) propagates CandidateConstructionError
    before any submission is attempted — the caller never rides a
    stale/asserted verdict."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-1",
            "subject": "s",
            "payload": {"rule": "modularity.class_too_large"},
            "created_at": None,
        }
    )
    build_candidate = AsyncMock(
        side_effect=CandidateConstructionError("Unknown validation run: run-1")
    )
    submit = AsyncMock()

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch("will.autonomy.lane_service.build_validated_candidate", build_candidate),
        patch("will.autonomy.lane_service.submit_assisted_lane_proposal", submit),
    ):
        with pytest.raises(CandidateConstructionError):
            await LaneService().propose_validated_diff(
                finding_id="f-1",
                patch="x",
                validation_run_id="run-1",
            )

    submit.assert_not_awaited()


async def test_propose_translates_submission_error_to_lane_propose_error():
    """A late-discovered ineligibility — a finding that stopped being a live
    lane item between the initial check and the atomic submission race
    window — surfaces from submit_assisted_lane_proposal as
    ProposalSubmissionError (ADR-154 D3b) and is translated to
    LaneProposeError so the API route's existing 409 mapping still applies;
    no new route-level exception handling is needed."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-1",
            "subject": "s",
            "payload": {"rule": "modularity.class_too_large"},
            "created_at": None,
        }
    )
    build_candidate = AsyncMock(return_value=_candidate())
    submit = AsyncMock(
        side_effect=ProposalSubmissionError(
            "1/1 finding(s) no longer eligible for deferral"
        )
    )

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch("will.autonomy.lane_service.build_validated_candidate", build_candidate),
        patch("will.autonomy.lane_service.submit_assisted_lane_proposal", submit),
    ):
        with pytest.raises(LaneProposeError, match="no longer eligible"):
            await LaneService().propose_validated_diff(
                finding_id="f-1",
                patch="x",
                validation_run_id="run-1",
            )


async def test_next_delegated_finding_returns_fifo_head_with_bundle():
    """next_delegated_finding asks for limit=1 and returns the head enriched
    with the #653 context bundle. A payload-less finding has no rule, so the
    bundle's rule id is None and remediation is None (no external deps hit)."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_findings = AsyncMock(return_value=[{"id": "f-1"}])

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        out = await LaneService().next_delegated_finding()

    assert out["id"] == "f-1"
    assert out["bundle"]["rule"]["id"] is None
    assert out["bundle"]["remediation"] is None
    bb_service.fetch_delegated_findings.assert_awaited_once_with(limit=1)


def _patch_bundle_sources(rationale: str | None, raises: bool, guidance):
    """Patch the bundle's intent reads: IntentRepository + remediation map."""
    repo = MagicMock()
    if raises:
        repo.get_rule.side_effect = GovernanceError("no such rule")
    else:
        rule_ref = MagicMock()
        rule_ref.content = {"rationale": rationale}
        repo.get_rule.return_value = rule_ref
    return (
        patch(
            "will.autonomy.lane_service.get_intent_repository",
            return_value=repo,
        ),
        patch(
            "will.autonomy.lane_service.load_remediation_guidance",
            return_value=guidance,
        ),
    )


async def test_get_finding_bundle_includes_rationale_and_remediation():
    """A live-rule finding's bundle carries rule rationale (in_registry True)
    and the remediation-map guidance."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-1",
            "subject": "s",
            "payload": {"rule": "modularity.class_too_large"},
            "created_at": None,
        }
    )
    guidance = {"description": "class refactor — human judgment", "status": "DELEGATE"}
    p_repo, p_rem = _patch_bundle_sources("classes must stay small", False, guidance)

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        p_repo,
        p_rem,
    ):
        out = await LaneService().get_finding_bundle("f-1")

    assert out["bundle"]["rule"]["in_registry"] is True
    assert out["bundle"]["rule"]["rationale"] == "classes must stay small"
    assert out["bundle"]["remediation"] == guidance


async def test_get_finding_bundle_flags_orphan_when_rule_absent():
    """A finding whose rule id is no longer in the registry (renamed/retired,
    cf. #657) is flagged in_registry=False rather than crashing."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-2",
            "subject": "s",
            "payload": {"rule": "architecture.intent.non_gateway_no_direct_resolution"},
            "created_at": None,
        }
    )
    p_repo, p_rem = _patch_bundle_sources(None, True, None)

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        p_repo,
        p_rem,
    ):
        out = await LaneService().get_finding_bundle("f-2")

    assert out["bundle"]["rule"]["in_registry"] is False
    assert out["bundle"]["rule"]["rationale"] is None


async def test_get_finding_bundle_none_when_not_live():
    """get_finding_bundle returns None when the finding is not a live lane item."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(return_value=None)
    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        assert await LaneService().get_finding_bundle("missing") is None


async def test_next_delegated_finding_empty_returns_none():
    """An empty lane yields None, not an IndexError."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_findings = AsyncMock(return_value=[])

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        assert await LaneService().next_delegated_finding() is None


async def test_claim_delegated_finding_true_when_row_updated():
    """claim returns True when the blackboard updated a live lane item."""
    bb_service = AsyncMock()
    bb_service.claim_delegated_finding = AsyncMock(return_value=1)

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        assert await LaneService().claim_delegated_finding("f-1", "claude-code") is True

    bb_service.claim_delegated_finding.assert_awaited_once_with("f-1", "claude-code")


async def test_claim_delegated_finding_false_when_not_live():
    """claim returns False when no row matched (not a live lane item)."""
    bb_service = AsyncMock()
    bb_service.claim_delegated_finding = AsyncMock(return_value=0)

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        assert await LaneService().claim_delegated_finding("missing", "x") is False
