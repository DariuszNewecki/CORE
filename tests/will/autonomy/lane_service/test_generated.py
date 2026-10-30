from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.lane_service import LaneService


# ID: ba82b21c-f606-4269-b6df-71a1a812369d
async def test_LaneService_propose_validated_diff():
    service = LaneService()

    bb_service = MagicMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={"payload": {"rule": "rule-x"}}
    )

    candidate = MagicMock()
    candidate.production_set = ["a.py", "b.py"]
    candidate.candidate_id = "cand-1"

    proposal = MagicMock()
    proposal_model = MagicMock()

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch(
            "will.autonomy.lane_service.build_validated_candidate",
            AsyncMock(return_value=candidate),
        ),
        patch(
            "will.autonomy.lane_service.build_assisted_lane_proposal",
            MagicMock(return_value=proposal),
        ),
        patch(
            "will.autonomy.lane_service.ProposalMapper.to_db_model",
            MagicMock(return_value=proposal_model),
        ),
        patch(
            "will.autonomy.lane_service.submit_assisted_lane_proposal",
            AsyncMock(return_value="prop-123"),
        ),
    ):
        proposal_id, production_set = await service.propose_validated_diff(
            finding_id="finding-1",
            patch="diff --git ...",
            validation_run_id="run-42",
        )

    assert proposal_id == "prop-123"
    assert production_set == ["a.py", "b.py"]
    bb_service.fetch_delegated_finding.assert_awaited_once_with("finding-1")


import pytest


@pytest.mark.asyncio
# ID: 3c78ebc0-9f8c-41a6-8222-4f1bf5d72382
async def test_LaneService_claim_delegated_finding():
    # Import symbol via its module path (class method)
    from will.autonomy.lane_service import LaneService

    instance = object.__new__(LaneService)

    mock_bb_service = AsyncMock()
    mock_bb_service.claim_delegated_finding = AsyncMock(return_value=1)

    mock_registry = AsyncMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_service)

    # Local import inside the method -> patch at defining module
    with patch(
        "body.services.service_registry.service_registry.get_blackboard_service",
        new=mock_registry.get_blackboard_service,
    ):
        result = await LaneService.claim_delegated_finding(
            instance, "finding-abc", "agent-x"
        )

    assert result is True
    mock_bb_service.claim_delegated_finding.assert_awaited_once_with(
        "finding-abc", "agent-x"
    )
