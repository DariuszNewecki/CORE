from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.v1.knowledge_routes import list_capabilities


@pytest.mark.asyncio
# ID: 1dea43a0-0671-4b8f-9060-2cc56959e095
async def test_list_capabilities():
    mock_session = AsyncMock()
    mock_caps = ["cap1", "cap2"]

    with patch("api.v1.knowledge_routes.KnowledgeService") as MockKnowledgeService:
        mock_service = AsyncMock()
        mock_service.list_capabilities = AsyncMock(return_value=mock_caps)
        MockKnowledgeService.return_value = mock_service

        result = await list_capabilities(session=mock_session)

        MockKnowledgeService.assert_called_once_with(session=mock_session)
        mock_service.list_capabilities.assert_awaited_once_with()
        assert result == {"capabilities": mock_caps}
