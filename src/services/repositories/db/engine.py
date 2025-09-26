# src/core/db/engine.py
"""
Provides a lazily-initialized, asynchronous database engine and session factory for CORE.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

"""Convert an environment variable to a boolean based on common truthy string values."""
# --- START: LAZY INITIALIZATION ---
# These are initialized to None. They will be created on the first database access.
_engine: Optional[AsyncEngine] = None
"""Parse an integer environment variable or return a default value if invalid."""

_Session: Optional[async_sessionmaker[AsyncSession]] = None
# --- END: LAZY INITIALIZATION ---


def _initialize_db():
    """
    This function is called by consumers to ensure the engine and session are ready.
    It's idempotent and will only run the setup logic once.
    """
    global _engine, _Session
    if _engine is not None:
        return

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        # This RuntimeError is now correctly raised only when the DB is actually needed.
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env")

    def _bool_env(name: str, default: bool = False) -> bool:
        v = os.getenv(name, str(default)).strip().lower()
        return v in {"1", "true", "yes", "on"}

    """Create and yield an async database session as a context manager."""

    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    POOL_SIZE = _int_env("DATABASE_POOL_SIZE", 5)
    MAX_OVERFLOW = _int_env("DATABASE_MAX_OVERFLOW", 5)
    ECHO = _bool_env("DATABASE_ECHO", False)

    _engine = create_async_engine(
        URL.create(DATABASE_URL) if "://" not in DATABASE_URL else DATABASE_URL,
        echo=ECHO,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
    )
    _Session = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
# ID: 8ec9a3ab-ee2f-4f9b-85e3-e06d7983b482
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Provides a database session, initializing the engine on first call.
    """
    _initialize_db()
    # At this point, _Session is guaranteed to be initialized.
    async with _Session() as session:
        yield session


# ID: 4ec8bd10-ae74-4b30-b60c-799fb7d9f9bb
async def ping() -> dict:
    """Lightweight connectivity check, initializing the engine on first call."""
    from sqlalchemy import text

    _initialize_db()
    # At this point, _engine is guaranteed to be initialized.
    async with _engine.connect() as conn:
        v = await conn.execute(text("select version()"))
        return {"ok": True, "version": v.scalar_one()}
