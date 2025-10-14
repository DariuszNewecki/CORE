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


# --- START MODIFICATION: Add FastAPI Dependency Provider ---
# ID: a5020e20-0b41-4790-b810-8b2354cad751
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A dedicated dependency provider for FastAPI routes.
    This yields the session and ensures it's closed after the request.
    """
    async with get_session() as session:
        yield session


# --- END MODIFICATION ---
