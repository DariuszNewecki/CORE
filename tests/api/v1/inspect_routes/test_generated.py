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


from unittest.mock import MagicMock

import pytest

from api.v1.inspect_routes import search_capabilities


@pytest.mark.asyncio
# ID: c014f8aa-84dd-4b39-b135-ef50b7f80b5a
async def test_search_capabilities():
    core_context = MagicMock()
    request = MagicMock()
    request.app.state.core_context = core_context

    expected = {"results": [{"id": "cap-1"}]}

    with patch(
        "api.v1.inspect_routes.get_search_capabilities",
        new=AsyncMock(return_value=expected),
    ) as mock_get:
        result = await search_capabilities(request=request, q="foo", limit=5)

    assert result == expected
    mock_get.assert_awaited_once_with(core_context, q="foo", limit=5)
