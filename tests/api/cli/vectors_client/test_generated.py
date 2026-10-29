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


import asyncio


# ID: a8e96f57-9f1e-45bd-b2ac-01fdb5a22a6a
def test_VectorsClient_status() -> None:
    facade = MagicMock()
    expected = {"collections": [{"name": "code", "status": "green"}]}
    facade._request = AsyncMock(return_value=expected)

    client = VectorsClient(facade)

    result = asyncio.run(client.status())

    assert result == expected
    facade._request.assert_awaited_once_with("GET", "/v1/vectors/status")



import pytest


@pytest.mark.asyncio
# ID: 35bb570c-dae3-4137-a167-8efe41a9eadf
async def test_VectorsClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})

    client = VectorsClient(facade)

    status_result = await client.status()
    assert status_result == {"ok": True}
    facade._request.assert_awaited_once_with("GET", "/v1/vectors/status")

    facade._request.reset_mock()
    query_result = await client.query("test query")
    assert query_result == {"ok": True}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/vectors/query",
        json={"query": "test query", "collection": "policies", "limit": 5},
    )

    facade._request.reset_mock()
    rebuild_result = await client.rebuild("policies", write=True)
    assert rebuild_result == {"ok": True}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/vectors/rebuild",
        json={"collection": "policies", "write": True},
    )
