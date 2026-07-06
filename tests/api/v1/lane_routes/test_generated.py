from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.v1.lane_routes import claim_delegated_finding


@pytest.mark.asyncio
# ID: 92a8c4fe-5fa1-409b-8cb2-37d13ee5d580
async def test_claim_delegated_finding():
    finding_id = "test-finding-uuid"
    agent = "test-agent"

    with patch("api.v1.lane_routes.LaneService") as mock_lane_service_class:
        mock_lane_service = AsyncMock()
        mock_lane_service_class.return_value = mock_lane_service
        mock_lane_service.claim_delegated_finding = AsyncMock(return_value=True)

        result = await claim_delegated_finding(finding_id=finding_id, agent=agent)

        mock_lane_service.claim_delegated_finding.assert_awaited_once_with(
            finding_id, agent
        )
        assert result == {
            "finding_id": finding_id,
            "claimed_by": agent,
            "status": "indeterminate",
        }
