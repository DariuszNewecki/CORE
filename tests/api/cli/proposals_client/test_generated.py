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


import pytest


@pytest.mark.asyncio
# ID: a981251c-f134-421b-9cb9-620e91447595
async def test_ProposalsClient_approve_proposal():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "approved"})

    client = ProposalsClient(facade)

    result = await client.approve_proposal(
        proposal_id="prop-123",
        approved_by="alice",
        approval_authority="admin",
    )

    assert result == {"status": "approved"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/proposals/prop-123/approve",
        json={
            "approved_by": "alice",
            "approval_authority": "admin",
        },
    )


import pytest


# ID: eef6a5fa-b6f0-486b-b2bf-1252ff1b7fea
async def test_get_proposal() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "prop-123", "title": "Example"})

    client = ProposalsClient(facade)

    result = await client.get_proposal("prop-123")

    assert result == {"id": "prop-123", "title": "Example"}
    facade._request.assert_awaited_once_with("GET", "/v1/proposals/prop-123")


import pytest


# ID: a9ac88fa-e2d0-432f-87ca-f56f7004bd9a
async def test_ProposalsClient_list_proposals():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"proposals": [{"id": "p1"}]})

    client = ProposalsClient(facade)

    result = await client.list_proposals(status="open", limit=10)

    facade._request.assert_awaited_once_with(
        "GET", "/v1/proposals", params={"limit": 10, "status": "open"}
    )
    assert result == {"proposals": [{"id": "p1"}]}


import pytest


@pytest.mark.asyncio
# ID: 05ae6771-cfc7-4845-b0cd-a0b73f715702
async def test_ProposalsClient_create_proposal():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "prop_123", "goal": "do the thing"})

    client = ProposalsClient(facade)

    result = await client.create_proposal("do the thing")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/proposals",
        json={
            "goal": "do the thing",
            "actions": [],
            "files": [],
            "created_by": "cli_operator",
            "write": True,
        },
    )
    assert result == {"id": "prop_123", "goal": "do the thing"}
