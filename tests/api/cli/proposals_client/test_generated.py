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


import pytest


@pytest.mark.asyncio
# ID: f700b343-acb6-4cee-8a14-9e2016991f06
async def test_ProposalsClient_execute_proposal() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "executed"})

    client = ProposalsClient(facade)

    result = await client.execute_proposal("prop-123", write=True)

    assert result == {"status": "executed"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/proposals/prop-123/execute",
        json={"write": True},
    )


import asyncio


# ID: c33638ae-ff31-4b18-9ec9-1da12baa38a7
def test_ProposalsClient_reject_proposal():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "rejected"})

    client = ProposalsClient(facade)

    result = asyncio.run(client.reject_proposal("prop-123", "not aligned with goals"))

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/proposals/prop-123/reject",
        json={"reason": "not aligned with goals"},
    )
    assert result == {"status": "rejected"}
