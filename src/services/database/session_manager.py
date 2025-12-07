# src/services/database/session_manager.py
"""
The single source of truth for creating and managing database sessions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.config import settings


_ENGINE: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=str(getattr(settings, "DATABASE_ECHO", "false")).lower() == "true",
    future=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
# ID: b35cd62e-6ada-4eee-b70b-ea20606e9d12
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Primary entry point for services that need a session with a 'with' block.
    """
    session: AsyncSession = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()


# ID: a5020e20-0b41-4790-b810-8b2354cad751
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A dedicated dependency provider for FastAPI routes.
    This yields the session and ensures it's closed after the request.
    """
    async with get_session() as session:
        yield session


# ID: 78c9a2b3-4d5e-6f7a-8b9c-0d1e2f3a4b5c
async def dispose_engine() -> None:
    """
    Gracefully dispose of the global database engine connection pool.
    Call this on application shutdown to avoid 'Event loop is closed' errors.
    """
    await _ENGINE.dispose()
