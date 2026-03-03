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
        This async generator yields a single AsyncSession for database use in FastAPI routes.
    Args:
    Returns: An AsyncGenerator yielding one AsyncSession.
    """
    """
    This async generator function get_api_session creates and yields an AsyncSession object for database interaction in FastAPI route handlers, returning the session once.
    """
    """
    Async generator function get_api_session creates and yields an AsyncSession object for database interaction in FastAPI route handlers, returning the session once.
    """
    """
    This Python function is an async generator that creates and yields an AsyncSession object for database interaction in FastAPI route handlers, which returns the session once.
    """
    """
    This Python function is an async generator that creates and yields an AsyncSession object, which can be used to interact with a database in FastAPI route handlers. It returns the session once and then stops yielding further sessions.
    """
    """
    The function get_api_session is a FastAPI dependency that asynchronously generates an AsyncSession object, which can be used to interact with the database in route handlers. It yields the session once and returns it as an asynchronous generator.
    """
    """
        FastAPI dependency that yields an async database session for route handlers.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession object.
    """
    """
        FastAPI dependency that yields an async database session for route handlers.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession object.
    """
    """
        FastAPI dependency that yields an async database session for route handlers.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession object.
    """
    """
    FastAPI dependency that yields an async database session for route handlers.
    """
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
        Opens and yields an asynchronous database session for background tasks.
    Args:
    Returns: An asynchronous generator yielding a single AsyncSession.
    """
    """
    Open and yield an asynchronous database session for background usage, not tied to a specific request lifecycle.
    """
    """
    Open and yield an asynchronous database session for background usage, not tied to a specific request lifecycle.
    """
    """
        Open and yield an asynchronous database session for background usage, not tied to a specific request lifecycle.

    Args:

    Returns: AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
    Open and yield an asynchronous database session for background usage, not tied to a specific request lifecycle. Args: Returns: AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
    Open and yield an asynchronous database session for background usage, not tied to a specific request lifecycle.
    """
    """
        Open a background database session for use outside the request lifecycle.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
        Open a background database session for use outside the request lifecycle.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
        Context manager that yields an async database session for use in background tasks, independent of the request lifecycle.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
        Context manager that yields an async database session for use in background tasks, independent of request lifecycle.
    Args:
    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator yielding a single AsyncSession.
    """
    """
    Context manager: yields a session for background tasks.

    Usage in background tasks:
        async with open_background_session() as session:
            ...
    """
    async with get_session() as session:
        yield session
