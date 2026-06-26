# tests/will/autonomy/test_lane_service.py

"""Unit tests for LaneService — Assisted Remediation Lane (ADR-109 #652).

LaneService is the Will-layer facade the lane API routes through. It owns no
state and no session; it delegates to the BlackboardService obtained from the
service_registry. The test stubs that registry call and asserts the limit is
forwarded and the rows passed straight back.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.intent.errors import GovernanceError
from will.autonomy.lane_service import LaneProposeError, LaneService


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


def _patch_proposals(create_mock: AsyncMock):
    """Patch ProposalService.open() to yield a stub service exposing create."""
    service = AsyncMock()
    service.create = create_mock

    @asynccontextmanager
    async def _open():
        yield service

    return patch("will.autonomy.lane_service.ProposalService.open", _open)


async def test_propose_validated_diff_creates_proposal_and_defers():
    """The happy path builds a human-gated, validation-gated, assisted-lane
    proposal that runs assisted.apply_diff with the patch, then defers the
    delegated finding to it (ADR-109 D3/D4)."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={
            "id": "f-1",
            "subject": "modularity.class_too_large::src/x.py",
            "payload": {"rule": "modularity.class_too_large"},
            "created_at": None,
        }
    )
    bb_service.defer_delegated_finding_to_proposal = AsyncMock(return_value=1)
    create = AsyncMock(return_value="prop-abc")

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        _patch_proposals(create),
    ):
        proposal_id = await LaneService().propose_validated_diff(
            finding_id="f-1",
            patch="--- a/src/x.py\n+++ b/src/x.py\n",
            production_set=["src/x.py", "src/base.py"],
        )

    assert proposal_id == "prop-abc"

    # The proposal handed to create carries the lane's mandatory shape.
    (proposal,), _ = create.call_args
    assert proposal.approval_required is True  # ADR-109 D3 — mandatory
    assert proposal.validation_checks == ["assisted.validate_diff"]
    assert proposal.validation_results == {"assisted.validate_diff": True}
    assert proposal.scope.files == ["src/x.py", "src/base.py"]
    assert proposal.constitutional_constraints["assisted_lane"] is True
    assert proposal.constitutional_constraints["finding_ids"] == ["f-1"]
    assert proposal.constitutional_constraints["rules"] == [
        "modularity.class_too_large"
    ]
    assert len(proposal.actions) == 1
    action = proposal.actions[0]
    assert action.action_id == "assisted.apply_diff"
    assert action.parameters["patch"] == "--- a/src/x.py\n+++ b/src/x.py\n"

    bb_service.defer_delegated_finding_to_proposal.assert_awaited_once_with(
        "f-1", "prop-abc"
    )


async def test_propose_raises_when_finding_not_live():
    """A finding that is not a live delegated lane item (None) raises
    LaneProposeError before any proposal is created."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(return_value=None)
    bb_service.defer_delegated_finding_to_proposal = AsyncMock()
    create = AsyncMock()

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        _patch_proposals(create),
    ):
        with pytest.raises(LaneProposeError):
            await LaneService().propose_validated_diff(
                finding_id="missing",
                patch="x",
                production_set=["src/x.py"],
            )

    create.assert_not_awaited()
    bb_service.defer_delegated_finding_to_proposal.assert_not_awaited()


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
