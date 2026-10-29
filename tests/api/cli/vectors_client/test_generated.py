from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.vectors_client import VectorsClient


@pytest.mark.asyncio
# ID: e8368cd3-835b-4026-b935-6da07307a5a9
async def test_VectorsClient_rebuild() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok"})

    client = VectorsClient(facade)

    result = await client.rebuild("my_collection", write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/vectors/rebuild",
        json={"collection": "my_collection", "write": True},
    )
    assert result == {"status": "ok"}
