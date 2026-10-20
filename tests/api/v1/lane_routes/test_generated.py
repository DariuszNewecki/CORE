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


from api.v1.lane_routes import propose_diff


# ID: b13640f0-a6c7-4547-ad0d-d0b75f1b257c
async def test_propose_diff():
    from api.v1.lane_routes import ProposeRequest

    body = ProposeRequest(
        patch="diff --git a/x b/x",
        validation_run_id="run-123",
    )

    mock_service = AsyncMock()
    mock_service.propose_validated_diff = AsyncMock(
        return_value=("proposal-abc", ["src/x.py", "tests/test_x.py"])
    )

    with patch("api.v1.lane_routes.LaneService", return_value=mock_service):
        result = await propose_diff(finding_id="finding-1", body=body)

    mock_service.propose_validated_diff.assert_awaited_once_with(
        finding_id="finding-1",
        patch=body.patch,
        validation_run_id="run-123",
    )
    assert result == {
        "proposal_id": "proposal-abc",
        "status": "pending",
        "approval_required": True,
        "scope_files": ["src/x.py", "tests/test_x.py"],
    }


from unittest.mock import MagicMock

import pytest

from api.v1.lane_routes import get_delegated_finding


@pytest.mark.asyncio
# ID: f656f723-6fca-4c68-81a1-09231ec71c47
async def test_get_delegated_finding():
    expected = {"id": "abc-123", "bundle": {"foo": "bar"}}

    with patch("api.v1.lane_routes.LaneService") as mock_lane_service_cls:
        mock_instance = MagicMock()
        mock_instance.get_finding_bundle = AsyncMock(return_value=expected)
        mock_lane_service_cls.return_value = mock_instance

        result = await get_delegated_finding(finding_id="abc-123")

    assert result == expected
    mock_instance.get_finding_bundle.assert_awaited_once_with("abc-123")



import pytest


@pytest.mark.asyncio
# ID: 3118d086-acde-4221-9905-22ed5aa91c20
async def test_next_delegated_finding():
    from api.v1.lane_routes import next_delegated_finding

    expected = {"id": 1, "status": "delegated"}

    with patch("api.v1.lane_routes.LaneService") as mock_lane_service_cls:
        mock_service = mock_lane_service_cls.return_value
        mock_service.next_delegated_finding = AsyncMock(return_value=expected)

        result = await next_delegated_finding()

    assert result == expected
    mock_service.next_delegated_finding.assert_awaited_once()
