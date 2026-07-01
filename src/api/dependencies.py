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
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.infrastructure.database.session_manager import get_db_session, get_session


# ID: 5b9f734c-5a1c-4278-9853-b0b841b08510
async def get_api_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session for route handlers.
    """
    async for session in get_db_session():
        yield session


# ID: 4b37e11c-2859-4e76-9d1b-e68c3050eed1
async def open_background_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Open and yield an async database session for use outside the request lifecycle.
    """
    async with get_session() as session:
        yield session


# ID: c3f7a2e9-1d4b-4e8c-b6f0-5a2d1c3e7f9b
async def get_current_user(
    core_access: Annotated[str | None, Cookie()] = None,
) -> dict:
    """Validate the core_access cookie and return the JWT payload.

    Raises 401 if the token is absent, expired, invalid, or the user is
    on the suspension deny-list (ADR-124 D4 — immediate suspension).
    Use as a FastAPI dependency on any protected route.
    """
    if not core_access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        from body.services.auth.tokens import decode_access_token

        payload = decode_access_token(core_access, settings.JWT_SECRET_KEY)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please refresh or log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    from body.services.auth.deny_list import deny_list

    if deny_list.is_denied(payload["sub"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account suspended.",
        )

    return payload


# ID: 7a1e5c3f-2b4d-4f9e-b8a0-6c2d1a7e5f3b
def require_role(*roles: str) -> Depends:
    """Return a FastAPI dependency that enforces one of the given roles."""

    async def _check(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    return Depends(_check)


require_governor = require_role("platform_admin")

require_operator = require_role("org_admin", "platform_admin")
