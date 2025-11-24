# tests/unit/test_service_registry.py
from unittest.mock import MagicMock, patch

import pytest

from src.body.services.service_registry import ServiceRegistry


@pytest.fixture
def registry():
    """Create a fresh ServiceRegistry instance for each test."""
    return ServiceRegistry()


@pytest.mark.asyncio
async def test_get_qdrant_service_is_singleton(registry):
    """
    Verify that calling get_qdrant_service twice returns the EXACT same instance
    and only imports/initializes once.
    """
    # Mock the slow imports inside the method
    with patch("services.clients.qdrant_client.QdrantService") as MockQdrant:
        # First call
        s1 = await registry.get_qdrant_service()

        # Second call
        s2 = await registry.get_qdrant_service()

        # Assertions
        assert s1 is s2, "Registry did not return a singleton instance"
        MockQdrant.assert_called_once()  # Constructor called only once


@pytest.mark.asyncio
async def test_get_cognitive_service_injects_dependencies(registry):
    """
    Verify that getting CognitiveService automatically creates and injects QdrantService.
    """
    # We mock both service classes to avoid real IO
    with patch(
        "will.orchestration.cognitive_service.CognitiveService"
    ) as MockCognitive:
        with patch("services.clients.qdrant_client.QdrantService") as MockQdrant:

            # Act: Request the dependent service
            cog_service = await registry.get_cognitive_service()

            # Assert: Qdrant was created implicitly
            assert "qdrant" in registry._instances

            # Assert: CognitiveService was initialized with repo_path AND qdrant_service
            MockCognitive.assert_called_once()
            call_kwargs = MockCognitive.call_args.kwargs

            assert "repo_path" in call_kwargs
            assert "qdrant_service" in call_kwargs
            assert isinstance(call_kwargs["qdrant_service"], MagicMock)  # It's our mock


@pytest.mark.asyncio
async def test_get_service_dynamic_resolution(registry, mocker):
    """
    Test that the legacy/dynamic string lookup delegates to the explicit factories.
    """
    # Spy on the explicit factory
    spy = mocker.spy(registry, "get_qdrant_service")

    # Mock the internal import so it doesn't fail
    with patch("services.clients.qdrant_client.QdrantService"):
        # Act via string name
        await registry.get_service("qdrant")

        # Assert delegation occurred
        spy.assert_awaited_once()
