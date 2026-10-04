# src/api/dependencies.py

"""
API Layer Dependency Providers.

CONSTITUTIONAL NOTE: This file is explicitly excluded from
architecture.api.no_direct_database_access enforcement. It is the
ONLY sanctioned location in the API layer that may import database
session primitives directly. All routes must acquire sessions through
these providers — never by importing session_manager themselves.

It is also the sanctioned DI root for Body services the API needs
(architecture.api.no_body_bypass excludes this file): routes take them as
``*Dep`` parameters instead of importing Body themselves (ADR-049 D1 S6).

OSS MODE: CORE runs in trusted-localhost mode — no authentication.
Multi-tenant UAC (users, orgs, API keys) lives in core-platform.
require_governor and require_operator are no-op pass-throughs here;
core-platform mounts real role guards on top when running in Console mode.
"""

from __future__ import annotations

import pwd
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.serve import PEER_CRED_EXTENSION
from body.analyzers.scout_analyzer import ScoutAnalyzer
from body.introspection.drift_service import run_drift_analysis_async
from body.introspection.generate_capability_docs import (
    main as _generate_capability_docs,
)
from body.services.consequence_log_service import ConsequenceLogService
from shared.infrastructure.database.session_manager import get_db_session, get_session
from shared.infrastructure.principal_binding import load_principal_binding
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


@dataclass(frozen=True)
# ID: e4c361b1-f851-4885-979c-8a03ccd07d1e
class CallerPrincipal:
    """Who called, as the kernel and the principal binding say (ADR-132 D10).

    ``uid`` is None on TCP, which carries no identity. ``role`` is None when
    the uid is unbound or the binding is unavailable (``binding_error``).
    """

    uid: int | None
    account: str | None
    role: str | None
    binding_error: str | None = None


# ID: d1aa4d9f-e173-4be9-a38a-07af629f5e2b
async def get_caller_principal(request: Request) -> CallerPrincipal:
    """Resolve the caller from the connection's kernel peer credentials.

    Not yet consulted by any gate: ``require_governor`` stays a pass-through
    until stamps and enforcement land together (ADR-132 D10.6 as amended).
    """
    extensions = request.scope.get("extensions") or {}
    peer_cred = extensions.get(PEER_CRED_EXTENSION)
    if peer_cred is None:
        return CallerPrincipal(uid=None, account=None, role=None)
    uid = int(peer_cred["uid"])
    try:
        account: str | None = pwd.getpwuid(uid).pw_name
    except KeyError:
        account = None
    binding = load_principal_binding()
    return CallerPrincipal(
        uid=uid,
        account=account,
        role=binding.role_for(uid),
        binding_error=binding.error,
    )


caller_principal = Depends(get_caller_principal)


# ID: 7854c52e-6493-402f-ba18-08ecdcf1fd2b
def get_consequence_log_service() -> ConsequenceLogService:
    """FastAPI dependency that provides a ConsequenceLogService instance."""
    return ConsequenceLogService()


ConsequenceLogDep = Annotated[
    ConsequenceLogService, Depends(get_consequence_log_service)
]


# ID: c33dd851-11fe-4f54-932e-d28096fe4563
def get_scout_analyzer() -> ScoutAnalyzer:
    """FastAPI dependency that provides the PARSE-phase ScoutAnalyzer."""
    return ScoutAnalyzer()


ScoutAnalyzerDep = Annotated[ScoutAnalyzer, Depends(get_scout_analyzer)]

DriftAnalysis = Callable[[], Awaitable[dict[str, Any]]]


# ID: a63c57c7-e5d4-4673-8437-32f9c40abf10
def get_drift_analysis() -> DriftAnalysis:
    """FastAPI dependency that provides the symbol-drift query (ADR-143 D3)."""
    return run_drift_analysis_async


DriftAnalysisDep = Annotated[DriftAnalysis, Depends(get_drift_analysis)]

CapabilityDocsGenerator = Callable[..., Awaitable[Any]]


# ID: 203436ea-62bc-4a91-90a4-572339e9ca9b
def get_capability_docs_generator() -> CapabilityDocsGenerator:
    """FastAPI dependency that provides the capability-reference generator."""
    return _generate_capability_docs


CapabilityDocsDep = Annotated[
    CapabilityDocsGenerator, Depends(get_capability_docs_generator)
]


# ID: 8d1ba106-fbed-41a1-8fe7-9452d612a29a
async def get_secrets_service_dep(
    session: AsyncSession = Depends(get_api_session),
) -> SecretsService:
    """FastAPI dependency that provides a SecretsService instance."""
    return await _get_secrets_svc(session)
