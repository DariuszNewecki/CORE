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



import pytest


@pytest.mark.asyncio
# ID: 067b9fe1-a8be-4155-b3b2-2703788818b7
async def test_VectorsClient_query():
    from api.cli.vectors_client import VectorsClient

    facade = MagicMock()
    facade._request = AsyncMock(return_value={"results": [{"id": "abc", "score": 0.9}]})

    client = VectorsClient(facade)

    result = await client.query("what is the refund policy?")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/vectors/query",
        json={
            "query": "what is the refund policy?",
            "collection": "policies",
            "limit": 5,
        },
    )
    assert result == {"results": [{"id": "abc", "score": 0.9}]}
