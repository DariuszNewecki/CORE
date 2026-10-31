from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.governance.inspect_runner import get_search_capabilities


@pytest.mark.asyncio
# ID: 35af6366-0dad-4a49-b8ac-f7d7b2e468ee
async def test_get_search_capabilities():
    context = MagicMock()
    context.cognitive_service = MagicMock()
    context.cognitive_service.search_capabilities = AsyncMock(
        return_value=[{"name": "cap_a"}, {"name": "cap_b"}]
    )

    result = await get_search_capabilities(context, q="search", limit=5)

    context.cognitive_service.search_capabilities.assert_awaited_once_with(
        "search", limit=5
    )
    assert result["query"] == "search"
    assert result["available"] is True
    assert result["count"] == 2
    assert result["results"] == [{"name": "cap_a"}, {"name": "cap_b"}]
