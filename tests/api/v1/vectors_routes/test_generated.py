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


import pytest

from api.v1.vectors_routes import vector_status


@pytest.mark.asyncio
# ID: d1d15f20-9338-4a01-8ebd-2e4f0965f06f
async def test_vector_status():
    # Build mock request with app.state.core_context
    mock_qdrant = MagicMock()
    mock_collection = MagicMock()
    mock_collection.name = "test_collection"
    mock_collections = MagicMock()
    mock_collections.collections = [mock_collection]
    mock_qdrant.client.get_collections = AsyncMock(return_value=mock_collections)
    mock_qdrant_service = MagicMock()
    mock_qdrant_service.qdrant_service = mock_qdrant
    mock_core_context = MagicMock()
    mock_core_context.qdrant_service = mock_qdrant
    mock_request = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    result = await vector_status(mock_request)
    assert result == {"collections": [{"name": "test_collection", "status": "active"}]}
    mock_qdrant.client.get_collections.assert_awaited_once()


from api.v1.vectors_routes import VectorRebuildRequest


# ID: 70e26b57-594f-48d3-ad15-b418958a5088
def test_VectorRebuildRequest():
    request = VectorRebuildRequest(collection="test_collection")
    assert request.collection == "test_collection"
    assert request.write is False


from api.v1.vectors_routes import VectorQueryRequest


# ID: 358e58a6-5314-4dfe-baef-ce6f073005eb
def test_VectorQueryRequest():
    # Test happy path initialization with defaults
    request = VectorQueryRequest(query="What are our data retention policies?")
    assert request.query == "What are our data retention policies?"
    assert request.collection == "policies"
    assert request.limit == 5

    # Test with explicit parameters
    custom_request = VectorQueryRequest(
        query="Incident response procedures",
        collection="security",
        limit=10,
    )
    assert custom_request.query == "Incident response procedures"
    assert custom_request.collection == "security"
    assert custom_request.limit == 10

    # Verify the schema enforces constitutional bounds on valid values
    boundary_request = VectorQueryRequest(
        query="test query",
        collection="policies",
        limit=50,
    )
    assert boundary_request.limit == 50
    assert boundary_request.collection == "policies"
    assert boundary_request.query == "test query"
