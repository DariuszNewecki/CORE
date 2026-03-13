# src/api/dependencies.py

"""
API Layer Dependency Providers.

CONSTITUTIONAL NOTE: This file is explicitly excluded from
architecture.api.no_direct_database_access enforcement. It is the
ONLY sanctioned location in the API layer that may import database
session primitives directly. All routes must acquire sessions through
these providers — never by importing session_manager themselves.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.session_manager import get_db_session, get_session


# ID: api-deps-session-provider
# ID: 5b9f734c-5a1c-4278-9853-b0b841b08510
async def get_api_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session for route handlers.
    """
    async for session in get_db_session():
        yield session


# ID: api-deps-background-session
# ID: 4b37e11c-2859-4e76-9d1b-e68c3050eed1
async def open_background_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Open and yield an async database session for use outside the request lifecycle.
    """
    async with get_session() as session:
        yield session
