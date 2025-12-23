# src/shared/infrastructure/database/session_manager.py
"""
The single source of truth for creating and managing database sessions.

Design:
- No module-level async engine/pool creation (prevents cross-loop reuse).
- Maintain a per-event-loop engine+sessionmaker cache.
- Provide deterministic disposal helpers for CLI/runtime teardown.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from weakref import WeakKeyDictionary

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass(frozen=True)
class _DbState:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


# Per-event-loop cache to prevent "Future attached to a different loop" issues.
_DB_BY_LOOP: WeakKeyDictionary[asyncio.AbstractEventLoop, _DbState] = (
    WeakKeyDictionary()
)


def _engine_echo() -> bool:
    return str(getattr(settings, "DATABASE_ECHO", "false")).lower() == "true"


def _create_state() -> _DbState:
    """
    Create a new engine + session factory.

    IMPORTANT:
    - This must only be called while a loop is running (loop-local resource).
    - It must not be executed at import time.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=_engine_echo(),
        future=True,
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _DbState(engine=engine, session_factory=factory)


def _get_state() -> _DbState:
    """
    Return loop-local DB state (engine + sessionmaker).

    Raises:
        RuntimeError: if called without a running event loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as e:
        raise RuntimeError(
            "Database session requested without a running event loop. "
            "All DB access must occur inside an async runtime (e.g., via CLI loop owner)."
        ) from e

    state = _DB_BY_LOOP.get(loop)
    if state is None:
        state = _create_state()
        _DB_BY_LOOP[loop] = state
        logger.debug("Initialized DB engine for loop id=%s", id(loop))
    return state


@asynccontextmanager
# ID: b35cd62e-6ada-4eee-b70b-ea20606e9d12
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Primary entry point for creating an AsyncSession in an async context manager.

    Usage:
        async with get_session() as session:
            ...
    """
    state = _get_state()
    session: AsyncSession = state.session_factory()
    try:
        yield session
    finally:
        await session.close()


# ID: a5020e20-0b41-4790-b810-8b2354cad751
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency provider for FastAPI routes.
    """
    async with get_session() as session:
        yield session


# ID: 78c9a2b3-4d5e-6f7a-8b9c-0d1e2f3a4b5c
async def dispose_engine() -> None:
    """
    Dispose the DB engine for the CURRENT running event loop.
    Use this for deterministic teardown in CLI runtimes.

    This is the only safe disposal primitive for production paths, because
    engines are loop-bound resources by design here.
    """
    loop = asyncio.get_running_loop()
    state = _DB_BY_LOOP.pop(loop, None)
    if state is None:
        return
    await state.engine.dispose()
    logger.debug("Disposed DB engine for loop id=%s", id(loop))


# ID: abf075ce-51c0-46ba-9458-7314712a7556
async def dispose_all_engines_for_current_loop_only() -> None:
    """
    Best-effort cleanup helper used primarily in tests.

    IMPORTANT:
    - Disposing engines created in OTHER loops from the CURRENT loop is not safe.
    - Therefore, this only disposes the current loop (same behavior as dispose_engine).
    """
    await dispose_engine()
