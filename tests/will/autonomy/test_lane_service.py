# tests/will/autonomy/test_lane_service.py

"""Unit tests for LaneService — Assisted Remediation Lane (ADR-109 #652).

LaneService is the Will-layer facade the lane API routes through. It owns no
state and no session; it delegates to the BlackboardService obtained from the
service_registry. The test stubs that registry call and asserts the limit is
forwarded and the rows passed straight back.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from will.autonomy.lane_service import LaneProposeError, LaneService


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ), _patch_proposals(create):
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


@pytest.mark.asyncio
async def test_propose_raises_when_finding_not_live():
    """A finding that is not a live delegated lane item (None) raises
    LaneProposeError before any proposal is created."""
    bb_service = AsyncMock()
    bb_service.fetch_delegated_finding = AsyncMock(return_value=None)
    bb_service.defer_delegated_finding_to_proposal = AsyncMock()
    create = AsyncMock()

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ), _patch_proposals(create):
        with pytest.raises(LaneProposeError):
            await LaneService().propose_validated_diff(
                finding_id="missing",
                patch="x",
                production_set=["src/x.py"],
            )

    create.assert_not_awaited()
    bb_service.defer_delegated_finding_to_proposal.assert_not_awaited()
