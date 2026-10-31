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
