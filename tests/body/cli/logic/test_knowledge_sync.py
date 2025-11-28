# tests/body/cli/logic/test_knowledge_sync.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from body.cli.logic.knowledge_sync.snapshot import (
    fetch_capabilities,
    fetch_links,
    fetch_symbols,
    run_snapshot,
)


# Helper to mock an async context manager
class AsyncContextManagerMock:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def mock_session():
    session = AsyncMock()

    # Default row structure for SELECTs
    row_mock = MagicMock()
    row_mock._mapping = {
        "id": "123",
        "name": "test",
        "symbol_id": "s1",
        "capability_id": "c1",
        "confidence": 1.0,
    }

    # Default result for SELECTs (iterable)
    select_result = MagicMock()
    select_result.__iter__.return_value = [row_mock]

    # Default result for INSERT/RETURNING (scalar_one)
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = "manifest-uuid"

    def execute_side_effect(stmt, *args, **kwargs):
        sql = str(stmt).upper()
        if "INSERT INTO" in sql or "UPDATE" in sql:
            return insert_result
        return select_result

    session.execute.side_effect = execute_side_effect

    # --- FIX IS HERE ---
    # Override .begin to return a context manager mock, NOT a coroutine
    session.begin = MagicMock(return_value=AsyncContextManagerMock(session))
    # -------------------

    return session


@pytest.fixture
def mock_get_session(mock_session):
    """
    Returns a MagicMock that behaves like the get_session() factory.
    It returns an AsyncContextManagerMock when called.
    """
    # This mock mimics the @asynccontextmanager factory function
    factory_mock = MagicMock(return_value=AsyncContextManagerMock(mock_session))
    return factory_mock


@patch("body.cli.logic.knowledge_sync.snapshot.get_session", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_fetch_capabilities(mock_get_session_factory, mock_session):
    # Configure the factory to return our async context manager
    mock_get_session_factory.return_value = AsyncContextManagerMock(mock_session)

    results = await fetch_capabilities()

    assert len(results) == 1
    assert results[0]["id"] == "123"
    args = mock_session.execute.call_args[0][0]
    assert "FROM core.capabilities" in str(args)


@patch("body.cli.logic.knowledge_sync.snapshot.get_session", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_fetch_symbols(mock_get_session_factory, mock_session):
    mock_get_session_factory.return_value = AsyncContextManagerMock(mock_session)

    results = await fetch_symbols()

    assert len(results) == 1
    args = mock_session.execute.call_args[0][0]
    assert "FROM core.symbols" in str(args)


@patch("body.cli.logic.knowledge_sync.snapshot.get_session", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_fetch_links(mock_get_session_factory, mock_session):
    mock_get_session_factory.return_value = AsyncContextManagerMock(mock_session)

    results = await fetch_links()

    assert len(results) == 1
    assert results[0]["confidence"] == 1.0


@patch("body.cli.logic.knowledge_sync.snapshot.get_session", new_callable=MagicMock)
@patch("body.cli.logic.knowledge_sync.snapshot.write_yaml")
@patch("body.cli.logic.knowledge_sync.snapshot.EXPORT_DIR")
@pytest.mark.asyncio
async def test_run_snapshot(
    mock_export_dir, mock_write_yaml, mock_get_session_factory, mock_session
):
    # Critical: use new_callable=MagicMock in @patch to prevent AsyncMock creation
    mock_get_session_factory.return_value = AsyncContextManagerMock(mock_session)

    mock_export_dir.mkdir.return_value = None
    mock_write_yaml.return_value = "sha256:test"

    await run_snapshot(env="test", note="unit test")

    # Verification
    # 4 selects (caps, syms, links, northstar) + 1 insert manifest + 4 insert digests = 9 calls
    assert mock_session.execute.call_count >= 5
    assert mock_write_yaml.call_count == 4
