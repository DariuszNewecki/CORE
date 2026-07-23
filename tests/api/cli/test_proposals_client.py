# tests/api/cli/test_proposals_client.py
"""Tests for api.cli.proposals_client.ProposalsClient.get_proposal_chain.

New method (ADR-155 spec §4 component map); the sibling methods on this
sub-client have no pre-existing test coverage to extend.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from api.cli.proposals_client import ProposalsClient


async def test_get_proposal_chain_calls_the_exact_id_route() -> None:
    facade = AsyncMock()
    facade._request = AsyncMock(return_value={"proposal": {"proposal_id": "pid-1"}})
    client = ProposalsClient(facade)

    result = await client.get_proposal_chain("pid-1")

    facade._request.assert_awaited_once_with("GET", "/v1/proposals/pid-1/chain")
    assert result == {"proposal": {"proposal_id": "pid-1"}}
