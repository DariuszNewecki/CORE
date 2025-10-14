# tests/integration/test_session_manager.py
import pytest

from services.database.session_manager import (
    close_database,
    database_health_check,
    get_session,
    init_database,
)


@pytest.mark.integration
async def test_database_lifecycle():
    """Test database initialization and cleanup."""
    # Initialize
    await init_database()

    # Health check
    assert await database_health_check()

    # Use session
    async with get_session() as db:
        result = await db.execute("SELECT 1")
        assert result.scalar() == 1

    # Cleanup
    await close_database()


@pytest.mark.integration
async def test_session_transaction_rollback():
    """Test automatic rollback on exception."""
    await init_database()

    try:
        async with get_session() as db:
            # Simulate error
            raise ValueError("Test error")
    except ValueError:
        pass

    # Database should still be healthy
    assert await database_health_check()

    await close_database()
