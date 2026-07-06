from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.v1.inspect_routes import search_commands


@pytest.mark.asyncio
# ID: cc780f26-5728-4e9c-b559-acfca54f204e
async def test_search_commands():
    mock_session = AsyncMock()
    mock_get_search_commands = AsyncMock(return_value={"commands": ["deploy", "merge"]})

    with patch("api.v1.inspect_routes.get_search_commands", mock_get_search_commands):
        result = await search_commands(q="deploy", limit=10, session=mock_session)

    assert result == {"commands": ["deploy", "merge"]}
    mock_get_search_commands.assert_awaited_once_with(
        mock_session, q="deploy", limit=10
    )
