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
    FastAPI dependency: yields a database session for route handlers.

    Usage in routes:
        # ID: ca0573f2-23b8-4aa8-9041-591a8246e67b
        async def my_route(session: AsyncSession = Depends(get_api_session)):
    """
    async for session in get_db_session():
        yield session


# ID: api-deps-background-session
# ID: 4b37e11c-2859-4e76-9d1b-e68c3050eed1
async def open_background_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager: yields a session for background tasks.

    Usage in background tasks:
        async with open_background_session() as session:
            ...
    """
    async with get_session() as session:
        yield session
