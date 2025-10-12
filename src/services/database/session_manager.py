# src/services/database/session_manager.py
"""
Refactored under dry_by_design.
Pattern: extract_module. This is the single source of truth for creating DB sessions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from shared.config import settings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Create async engine from env URL (tests set this)
_ENGINE: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=str(getattr(settings, "DATABASE_ECHO", "false")).lower() == "true",
    future=True,
)

# IMPORTANT: use async_sessionmaker (not sessionmaker)
AsyncSessionFactory = async_sessionmaker(
    bind=_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
# ID: b35cd62e-6ada-4eee-b70b-ea20606e9d12
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Primary entry point used across the app.
    Yields an AsyncSession that shares the same engine as tests.
    """
    session: AsyncSession = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()
