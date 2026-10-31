from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.llm_resources_client import LlmResourcesClient


# ID: 8b003cdb-0348-4e4e-8ebb-cb132d4ccf1e
async def test_LlmResourcesClient_author() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "id": "res-1"})
    client = LlmResourcesClient(facade)

    definition = {"name": "demo", "model": "gpt-x"}
    result = await client.author(definition, write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/llm-resources/author",
        json={"definition": definition, "write": True},
    )
    assert result == {"ok": True, "id": "res-1"}



import pytest


@pytest.mark.asyncio
# ID: 9adfc034-98f3-4a13-a7d2-a099d99475cd
async def test_LlmResourcesClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "id": "abc"})

    client = LlmResourcesClient(facade)

    definition = {"name": "example", "role": "assistant"}
    result = await client.author(definition, write=True)

    assert result == {"ok": True, "id": "abc"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/llm-resources/author",
        json={"definition": definition, "write": True},
    )
