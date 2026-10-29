from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.proposals_client import ProposalsClient


# ID: dd58a915-5853-442f-924b-37363f6b6971
async def test_ProposalsClient_get_proposal_chain():
    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={
            "finding": {"id": "f1"},
            "proposal": {"id": "p1"},
            "consequence": {"id": "c1"},
        }
    )
    client = ProposalsClient(facade)

    result = await client.get_proposal_chain("prop-123")

    facade._request.assert_awaited_once_with("GET", "/v1/proposals/prop-123/chain")
    assert result == {
        "finding": {"id": "f1"},
        "proposal": {"id": "p1"},
        "consequence": {"id": "c1"},
    }
