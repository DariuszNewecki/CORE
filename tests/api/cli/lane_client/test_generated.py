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
