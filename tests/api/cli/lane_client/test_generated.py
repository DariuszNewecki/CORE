from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.lane_client import LaneClient


# ID: 4afa3f2c-8959-40a6-b188-a223cc82e485
async def test_LaneClient_propose() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={"proposal_id": "p-1", "status": "created"}
    )

    client = LaneClient(facade)
    result = await client.propose(
        finding_id="finding-42",
        patch="--- a/x\n+++ b/x\n",
        validation_run_id="run-abc",
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/lane/finding-42/propose",
        json={"patch": "--- a/x\n+++ b/x\n", "validation_run_id": "run-abc"},
    )
    assert result == {"proposal_id": "p-1", "status": "created"}


import pytest


@pytest.mark.asyncio
# ID: e570ed9d-716b-4977-8633-6818a3b9470b
async def test_LaneClient_claim() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})

    client = LaneClient(facade)
    result = await client.claim("finding-123", "agent-7")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/lane/finding-123/claim",
        params={"agent": "agent-7"},
    )
    assert result == {"ok": True}




# ID: cea6b1a0-41a9-4560-a2ac-0e17a006cd18
async def test_LaneClient():
    facade = MagicMock()
    facade._request = AsyncMock(side_effect=[{"ok": "claim"}, {"ok": "propose"}])

    client = LaneClient(facade)

    claim_result = await client.claim("finding-1", "agent-1")
    assert claim_result == {"ok": "claim"}
    facade._request.assert_awaited_with(
        "POST",
        "/v1/lane/finding-1/claim",
        params={"agent": "agent-1"},
    )

    propose_result = await client.propose("finding-1", "diff-patch", "run-42")
    assert propose_result == {"ok": "propose"}
    facade._request.assert_awaited_with(
        "POST",
        "/v1/lane/finding-1/propose",
        json={"patch": "diff-patch", "validation_run_id": "run-42"},
    )
