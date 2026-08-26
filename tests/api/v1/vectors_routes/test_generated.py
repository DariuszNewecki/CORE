from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.vectors_routes import vector_query


# ID: dfdf6006-f810-4815-8bdb-27b8ba34e53c
async def test_vector_query():
    # Arrange
    mock_request = MagicMock()
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_qdrant = MagicMock()
    mock_cognitive = MagicMock()
    mock_core_context.qdrant_service = mock_qdrant
    mock_core_context.cognitive_service = mock_cognitive

    mock_query_result = [{"id": 1}, {"id": 2}]
    mock_service_query = AsyncMock(return_value=mock_query_result)

    body = MagicMock()
    body.collection = "policies"
    body.query = "some query"
    body.limit = 5

    with (
        patch(
            "api.v1.vectors_routes.CognitiveEmbedderAdapter",
            return_value=MagicMock(),
        ),
        patch(
            "api.v1.vectors_routes.VectorIndexService",
            return_value=MagicMock(query=mock_service_query),
        ),
    ):
        # Act
        result = await vector_query(body, mock_request)

    # Assert
    assert result == {
        "results": mock_query_result,
        "collection": "core_policies",
        "count": 2,
    }
    mock_service_query.assert_awaited_once_with("some query", limit=5)
