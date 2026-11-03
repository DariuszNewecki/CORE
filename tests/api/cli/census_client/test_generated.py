from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.census_client import CensusClient


# ID: 56f51aa3-8a98-421f-aba0-ee9a271e4a67
async def test_CensusClient_census_diff() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"diff": []})

    client = CensusClient(facade)

    result = await client.census_diff(baseline="b123")

    facade._request.assert_awaited_once_with(
        "GET", "/v1/census/diff", params={"baseline": "b123"}
    )
    assert result == {"diff": []}
