# tests/api/v1/test_knowledge_routes.py

"""Unit tests for knowledge_routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from api.v1.knowledge_routes import list_capabilities


async def test_list_capabilities_returns_capabilities_wrapped():
    """GET /knowledge/capabilities delegates to KnowledgeService and wraps result."""
    caps = [
        {"name": "code_generation", "namespace": "framework"},
        {"name": "test_generation", "namespace": "framework"},
    ]
    session = AsyncMock()
    with patch("api.v1.knowledge_routes.KnowledgeService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.list_capabilities = AsyncMock(return_value=caps)
        mock_svc_cls.return_value = mock_svc

        out = await list_capabilities(session=session)

    assert out == {"capabilities": caps}
    mock_svc_cls.assert_called_once_with(session=session)
    mock_svc.list_capabilities.assert_awaited_once()


async def test_list_capabilities_empty_graph_returns_empty_list():
    """Empty knowledge graph returns empty list — not 404."""
    session = AsyncMock()
    with patch("api.v1.knowledge_routes.KnowledgeService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.list_capabilities = AsyncMock(return_value=[])
        mock_svc_cls.return_value = mock_svc

        out = await list_capabilities(session=session)

    assert out == {"capabilities": []}
