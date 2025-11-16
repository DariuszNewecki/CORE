from unittest.mock import AsyncMock, MagicMock

import pytest

from src.body.services.service_registry import ServiceRegistry


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
            MockRow("test_service", "src.body.services.test_service.TestService"),
            MockRow("another_service", "src.body.services.another.AnotherService"),
        ]
    )

    session.execute = AsyncMock(return_value=mock_result)

    # Mock the context manager properly
    @asynccontextmanager
    async def mock_get_session():
        yield session

    # FIX: Use the correct import path
    mocker.patch(
        "src.body.services.service_registry.get_session",
        return_value=mock_get_session(),
    )
    return session


@pytest.fixture
def registry():
    """Create a fresh ServiceRegistry instance for each test."""
    return ServiceRegistry()


@pytest.mark.asyncio
async def test_registry_initializes_from_database(registry, mock_db_session):
    """Tests that the registry loads service mappings from the database."""
    # Force initialization
    await registry._initialize_from_db()

    assert registry._initialized is True
    assert "test_service" in registry._service_map
    assert "another_service" in registry._service_map


@pytest.mark.asyncio
async def test_registry_only_initializes_once(registry, mock_db_session):
    """Tests that the registry doesn't re-initialize on subsequent calls."""
    await registry._initialize_from_db()
    await registry._initialize_from_db()

    # Should only query database once
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_service_raises_on_unknown_service(registry):
    """Tests that getting an unknown service raises an error."""
    # Don't initialize from DB - start with empty registry
    registry._initialized = True

    with pytest.raises(
        ValueError, match="Service 'unknown_service' not found in registry."
    ):
        await registry.get_service("unknown_service")


@pytest.mark.asyncio
async def test_get_service_returns_singleton(registry, mock_db_session, mocker):
    """Tests that the same service instance is returned on multiple calls."""
    # Mock the service class
    mock_service_class = MagicMock(return_value="service_instance")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # First, let's manually add a service to the registry so it doesn't try to initialize from DB
    registry._initialized = True
    registry._service_map["test_service"] = "src.body.services.test_service.TestService"

    # Get service twice
    service1 = await registry.get_service("test_service")
    service2 = await registry.get_service("test_service")

    assert service1 is service2
    assert service1 == "service_instance"
    # Should only create one instance (called with no args for regular services)
    mock_service_class.assert_called_once_with()


def test_import_class_loads_module_dynamically(registry):
    """Tests that _import_class can dynamically load a Python class."""
    # Use the ServiceRegistry class itself since we know it exists
    result = registry._import_class(
        "src.body.services.service_registry.ServiceRegistry"
    )
    assert result is not None
    assert result.__name__ == "ServiceRegistry"


@pytest.mark.asyncio
async def test_get_service_with_repo_path_services(registry, mocker):
    """Tests services that require repo_path argument."""
    mock_service_class = MagicMock(return_value="repo_service")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # Manually add service to avoid DB initialization
    registry._initialized = True
    registry._service_map["knowledge_service"] = (
        "src.body.services.knowledge.KnowledgeService"
    )

    # FIX: get_service() doesn't take repo_path parameter - it's set in constructor
    # For services that need repo_path, it's passed automatically based on service name
    service = await registry.get_service("knowledge_service")

    assert service == "repo_service"
    # Should be called with repo_path since it's in the special list
    mock_service_class.assert_called_once_with(registry.repo_path)


@pytest.mark.asyncio
async def test_get_service_with_no_args_services(registry, mocker):
    """Tests services that don't require any arguments."""
    mock_service_class = MagicMock(return_value="simple_service")
    mocker.patch.object(registry, "_import_class", return_value=mock_service_class)

    # Manually add service to avoid DB initialization
    registry._initialized = True
    registry._service_map["simple_service"] = "src.body.services.simple.SimpleService"

    service = await registry.get_service("simple_service")

    assert service == "simple_service"
    # Should be called with no arguments for regular services
    mock_service_class.assert_called_once_with()


@pytest.mark.asyncio
async def test_registry_handles_db_initialization_failure(registry, mocker):
    """Tests that registry handles database failures gracefully."""

    # Mock get_session to raise an exception
    async def failing_session():
        raise Exception("Database connection failed")
        yield

    # FIX: Use the correct import path
    mocker.patch(
        "src.body.services.service_registry.get_session", return_value=failing_session()
    )

    # The registry should handle this gracefully
    await registry._initialize_from_db()
    # Should not be initialized if DB fails
    assert registry._initialized is False


def test_registry_thread_safety_with_lock(registry):
    """Tests that the registry uses a lock for thread safety."""
    assert hasattr(registry, "_lock")
    assert registry._lock is not None


def test_import_class_handles_invalid_path(registry):
    """Tests that _import_class handles invalid module paths."""
    # FIX: _import_class takes a single string argument
    with pytest.raises(ImportError):
        registry._import_class("nonexistent.module.NonExistentClass")


def test_import_class_handles_missing_class(registry):
    """Tests that _import_class handles missing class names."""
    # FIX: _import_class takes a single string argument
    with pytest.raises(AttributeError):
        registry._import_class("src.shared.time.NonExistentClass")
