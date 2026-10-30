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
