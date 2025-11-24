# tests/will/orchestration/test_cognitive_service_unit.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.orchestration.cognitive_service import CognitiveService


@pytest.fixture
def mock_qdrant():
    return MagicMock()


@pytest.fixture
def service(tmp_path, mock_qdrant):
    """
    Create a CognitiveService with a mocked QdrantService injected.
    This proves the DI architecture works.
    """
    return CognitiveService(repo_path=tmp_path, qdrant_service=mock_qdrant)


@pytest.mark.asyncio
async def test_initialization_stores_dependencies(service, mock_qdrant):
    """Verify the service holds onto its injected dependencies."""
    assert service.qdrant_service is mock_qdrant


def test_missing_dependency_raises_error(tmp_path):
    """
    Constitutional Check: Ensure we fail fast if dependencies are missing.
    This prevents 'Split-Brain' (creating a hidden instance).
    """
    # Initialize WITHOUT Qdrant
    broken_service = CognitiveService(repo_path=tmp_path, qdrant_service=None)

    # Accessing the property should raise RuntimeError
    with pytest.raises(RuntimeError, match="was not injected"):
        _ = broken_service.qdrant_service


@pytest.mark.asyncio
async def test_search_capabilities_uses_injected_service(service, mock_qdrant):
    """Verify semantic search uses the INJECTED qdrant instance."""
    # Setup mocks
    service._loaded = True  # Skip DB load
    service.get_embedding_for_code = AsyncMock(return_value=[0.1, 0.2])
    mock_qdrant.search_similar = AsyncMock(return_value=[{"id": 1}])

    # Act
    results = await service.search_capabilities("query")

    # Assert
    assert results == [{"id": 1}]
    mock_qdrant.search_similar.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_embedding_delegates_to_client(service):
    """Verify embedding generation delegates to the specific client role."""
    mock_client = AsyncMock()
    mock_client.get_embedding.return_value = [0.9, 0.9]

    # Patch the internal helper to return our mock client
    service.aget_client_for_role = AsyncMock(return_value=mock_client)

    result = await service.get_embedding_for_code("print('hello')")

    assert result == [0.9, 0.9]
    service.aget_client_for_role.assert_awaited_with("Vectorizer")
