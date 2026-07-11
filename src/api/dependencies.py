# src/api/dependencies.py

"""
API Layer Dependency Providers.

CONSTITUTIONAL NOTE: This file is explicitly excluded from
architecture.api.no_direct_database_access enforcement. It is the
ONLY sanctioned location in the API layer that may import database
session primitives directly. All routes must acquire sessions through
these providers — never by importing session_manager themselves.

OSS MODE: CORE runs in trusted-localhost mode — no authentication.
Multi-tenant UAC (users, orgs, API keys) lives in core-platform.
require_governor and require_operator are no-op pass-throughs here;
core-platform mounts real role guards on top when running in Console mode.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.consequence_log_service import ConsequenceLogService
from shared.infrastructure.database.session_manager import get_db_session, get_session
from shared.infrastructure.secrets_service import SecretsService
from shared.infrastructure.secrets_service import (
    get_secrets_service as _get_secrets_svc,
)


# ID: 5b9f734c-5a1c-4278-9853-b0b841b08510
async def get_api_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session for route handlers."""
    async for session in get_db_session():
        yield session


# ID: 4b37e11c-2859-4e76-9d1b-e68c3050eed1
async def open_background_session() -> AsyncGenerator[AsyncSession, None]:
    """Open and yield an async database session for use outside the request lifecycle."""
    async with get_session() as session:
        yield session


# ID: d0a70ac3-7799-46e5-9e02-0fea32a6b144
async def _oss_passthrough() -> dict:
    """OSS mode: trusted localhost — no authentication required."""
    return {}


require_governor = Depends(_oss_passthrough)
require_operator = Depends(_oss_passthrough)


# ID: 7854c52e-6493-402f-ba18-08ecdcf1fd2b
def get_consequence_log_service() -> ConsequenceLogService:
    """FastAPI dependency that provides a ConsequenceLogService instance."""
    return ConsequenceLogService()


# ID: 8d1ba106-fbed-41a1-8fe7-9452d612a29a
async def get_secrets_service_dep(
    session: AsyncSession = Depends(get_api_session),
) -> SecretsService:
    """FastAPI dependency that provides a SecretsService instance."""
    return await _get_secrets_svc(session)
