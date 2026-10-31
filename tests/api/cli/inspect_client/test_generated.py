from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.inspect_client import InspectClient


@pytest.mark.asyncio
# ID: ab0443ce-f209-4fea-9aed-f85785b0f712
async def test_InspectClient_analysis_bridges() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"bridges": [{"name": "b1"}]})

    client = InspectClient(facade)

    result = await client.analysis_bridges(consuming="service_a")

    assert result == {"bridges": [{"name": "b1"}]}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/analysis/bridges", params={"consuming": "service_a"}
    )


import pytest


@pytest.mark.asyncio
# ID: 8a1b856a-cc21-45a8-89e2-4abaa8723e3f
async def test_InspectClient_refusals_stats():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"total": 5, "by_type": {"x": 5}})
    client = InspectClient(facade)

    result = await client.refusals_stats(days=14)

    assert result == {"total": 5, "by_type": {"x": 5}}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/refusals/stats", params={"days": 14}
    )



import pytest


@pytest.mark.asyncio
# ID: 4a24d1f4-3bc6-4136-b7f8-9f97152c748f
async def test_InspectClient_refusals_list():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"items": []})

    client = InspectClient(facade)

    result = await client.refusals_list()

    facade._request.assert_awaited_once_with(
        "GET", "/v1/refusals", params={"limit": 50}
    )
    assert result == {"items": []}
