# tests/unit/test_service_registry.py
"""
Tests for the ServiceRegistry dependency injection container.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.service_registry import ServiceRegistry


@pytest.fixture
def mock_db_session(mocker):
    """Mock database session for testing."""
    from contextlib import asynccontextmanager

    session = AsyncMock()

    # Create mock row objects with name and implementation attributes
    class MockRow:
        def __init__(self, name, implementation):
            self.name = name
            self.implementation = implementation

    mock_result = MagicMock()
    # The __iter__ makes it work with "for row in result"
    mock_result.__iter__ = lambda self: iter(
        [
            MockRow("test_service", "core.test_service.TestService"),
            MockRow("another_service", "core.another.AnotherService"),
        ]
    )

    session.execute = AsyncMock(return_value=mock_result)

    # Mock the context manager properly
    @asynccontextmanager
    async def mock_get_session():
        yield session

    mocker.patch("core.service_registry.get_session", return_value=mock_get_session())
    return session


@pytest.fixture
def registry(tmp_path):
    """Create a fresh ServiceRegistry instance."""
    # Reset class variables for each test
    ServiceRegistry._instances = {}
    ServiceRegistry._service_map = {}
    ServiceRegistry._initialized = False

    return ServiceRegistry(repo_path=tmp_path)


@pytest.mark.asyncio
async def test_registry_initializes_from_database(registry, mock_db_session):
    """Tests that the registry loads service mappings from the database."""
    # Force initialization
    await registry._initialize_from_db()

    assert registry._initialized is True
    assert "test_service" in registry._service_map
    assert "another_service" in registry._service_map
    assert registry._service_map["test_service"] == "core.test_service.TestService"


@pytest.mark.asyncio
async def test_registry_only_initializes_once(registry, mock_db_session):
    """Tests that the registry doesn't re-initialize on subsequent calls."""
    await registry._initialize_from_db()
    await registry._initialize_from_db()

    # Should only query database once
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_service_raises_on_unknown_service(registry, mock_db_session):
    """Tests that requesting an unknown service raises ValueError."""
    with pytest.raises(ValueError, match="Service 'nonexistent' not found"):
        await registry.get_service("nonexistent")


@pytest.mark.asyncio
async def test_get_service_returns_singleton(registry, mock_db_session, mocker):
    """Tests that the same service instance is returned on multiple calls."""
    # Mock the service class
    mock_service_class = MagicMock(return_value="service_instance")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # Get service twice
    service1 = await registry.get_service("test_service")
    service2 = await registry.get_service("test_service")

    # Should be the same instance
    assert service1 is service2
    # Should only instantiate once
    mock_service_class.assert_called_once()


@pytest.mark.asyncio
async def test_import_class_loads_module_dynamically(registry):
    """Tests that _import_class can dynamically import a class."""
    # Use a real class from the standard library
    cls = registry._import_class("pathlib.Path")

    assert cls is Path


@pytest.mark.asyncio
async def test_get_service_with_repo_path_services(registry, mock_db_session, mocker):
    """Tests that certain services are initialized with repo_path."""
    mock_service_class = MagicMock(return_value="service_with_path")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # Override service map to use a known service that needs repo_path
    registry._service_map["knowledge_service"] = (
        "core.knowledge_service.KnowledgeService"
    )
    registry._initialized = True

    service = await registry.get_service("knowledge_service")

    # Should be called with repo_path
    mock_service_class.assert_called_once_with(registry.repo_path)


@pytest.mark.asyncio
async def test_get_service_with_no_args_services(registry, mocker):
    """Tests that regular services are initialized without arguments."""
    # Manually populate the service map (bypassing database)
    registry._service_map = {"test_service": "core.test_service.TestService"}
    registry._initialized = True

    mock_service_class = MagicMock(return_value="regular_service")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    service = await registry.get_service("test_service")

    # Should be called without arguments
    mock_service_class.assert_called_once_with()
    assert service == "regular_service"


@pytest.mark.asyncio
async def test_registry_handles_db_initialization_failure(registry, mocker):
    """Tests that registry handles database failures gracefully."""

    # Mock get_session to raise an exception
    async def failing_session():
        raise Exception("Database connection failed")
        yield

    mocker.patch("core.service_registry.get_session", return_value=failing_session())

    # Should not raise, but should log error
    await registry._initialize_from_db()

    assert registry._initialized is False


@pytest.mark.asyncio
async def test_registry_thread_safety_with_lock(registry, mocker):
    """Tests that concurrent initialization attempts are serialized."""
    import asyncio

    # Manually populate the service map
    registry._service_map = {"test_service": "core.test_service.TestService"}
    registry._initialized = True

    # Mock a service class
    mock_service_class = MagicMock(return_value="test_service_instance")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # Try to get the same service concurrently
    results = await asyncio.gather(
        registry.get_service("test_service"),
        registry.get_service("test_service"),
        registry.get_service("test_service"),
    )

    # Should only instantiate once due to singleton pattern
    mock_service_class.assert_called_once()

    # All results should be the same instance
    assert results[0] is results[1]
    assert results[1] is results[2]


def test_import_class_handles_invalid_path(registry):
    """Tests that _import_class raises on invalid module path."""
    with pytest.raises(Exception):  # Could be ImportError or AttributeError
        registry._import_class("nonexistent.module.Class")


def test_import_class_handles_missing_class(registry):
    """Tests that _import_class raises when class doesn't exist in module."""
    with pytest.raises(AttributeError):
        registry._import_class("pathlib.NonexistentClass")
