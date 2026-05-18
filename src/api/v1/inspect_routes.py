# src/api/v1/inspect_routes.py

"""
Inspect API endpoints (ADR-057 Phase 3, D3, D5).

Every endpoint here is read-only — no resource tables, no background
tasks. Endpoints live under six top-level namespaces (`/status`,
`/decisions`, `/refusals`, `/analysis`, `/components`, `/search`) so the
API surface mirrors the CLI command groups one-to-one. All six routers
are mounted under the `Inspect` OpenAPI tag — `inspect` is the logical
namespace name, not a URL prefix (per ADR-053 D4 amendment 2026-05-18).

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session only.
- CoreContext is read from request.app.state.core_context.
- body.* repositories / mind.* engines / will.* services are reached
  through the will.governance.inspect_runner facade — no direct
  imports here (architecture.api.no_body_bypass).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.inspect_runner import (
    get_analysis_clusters,
    get_analysis_command_tree,
    get_analysis_common_knowledge,
    get_analysis_duplicates,
    get_analysis_test_targets,
    get_components_list,
    get_db_status,
    get_decisions,
    get_decisions_patterns,
    get_drift_status,
    get_refusals,
    get_refusals_stats,
    get_search_capabilities,
)


logger = getLogger(__name__)


# Each top-level namespace gets its own router. They are mounted together
# in api/main.py so the URL prefixes are preserved verbatim.
status_router = APIRouter(prefix="/status")
decisions_router = APIRouter(prefix="/decisions")
refusals_router = APIRouter(prefix="/refusals")
analysis_router = APIRouter(prefix="/analysis")
components_router = APIRouter(prefix="/components")
search_router = APIRouter(prefix="/search")


# ---------- /status ------------------------------------------------------


@status_router.get("/db")
# ID: 1c5d7e3f-4a6b-4c8d-9e0f-1a2b3c4d5e61
async def status_db(session: AsyncSession = Depends(get_api_session)) -> dict:
    """Return DB connection and schema state."""
    return await get_db_status(session)


@status_router.get("/drift")
# ID: 2d6e8f4a-5b7c-4d9e-0f1a-2b3c4d5e6f72
async def status_drift(
    request: Request,
    scope: str = Query(default="all"),
) -> dict:
    """Return consolidated drift snapshot for symbols and/or vectors."""
    core_context: CoreContext = request.app.state.core_context
    return await get_drift_status(core_context, scope=scope)


# ---------- /decisions ---------------------------------------------------


@decisions_router.get("")
# ID: 3e7f9a5b-6c8d-4e0f-1a2b-3c4d5e6f7a83
async def decisions_list(
    session_id: str | None = Query(default=None),
    agent: str | None = Query(default=None),
    pattern: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Return recent decision traces with optional filters."""
    return await get_decisions(
        session_id=session_id,
        agent=agent,
        pattern=pattern,
        limit=limit,
    )


@decisions_router.get("/patterns")
# ID: 4f8a0b6c-7d9e-4f1a-2b3c-4d5e6f7a8b94
async def decisions_patterns(
    days: int = Query(default=7, ge=1, le=365),
) -> dict:
    """Return pattern classification stats across the lookback window."""
    return await get_decisions_patterns(days=days)


# ---------- /refusals ----------------------------------------------------


@refusals_router.get("")
# ID: 5a9b1c7d-8e0f-4a2b-3c4d-5e6f7a8b9ca5
async def refusals_list(
    refusal_type: str | None = Query(default=None, alias="type"),
    session_id: str | None = Query(default=None, alias="session"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Return recent constitutional refusal records."""
    return await get_refusals(
        refusal_type=refusal_type,
        session_id=session_id,
        limit=limit,
    )


@refusals_router.get("/stats")
# ID: 6b0c2d8e-9f1a-4b3c-4d5e-6f7a8b9c0db6
async def refusals_stats(
    days: int = Query(default=7, ge=1, le=365),
) -> dict:
    """Return refusal statistics grouped by type."""
    return await get_refusals_stats(days=days)


# ---------- /analysis ----------------------------------------------------


@analysis_router.get("/clusters")
# ID: 7c1d3e9f-0a2b-4c4d-5e6f-7a8b9c0d1ec7
async def analysis_clusters(
    limit: int = Query(default=25, ge=1, le=200),
) -> dict:
    """Return semantic capability clusters."""
    return await get_analysis_clusters(limit=limit)


@analysis_router.get("/duplicates")
# ID: 8d2e4f0a-1b3c-4d5e-6f7a-8b9c0d1e2fd8
async def analysis_duplicates(
    request: Request,
    threshold: float = Query(default=0.85, ge=0.0, le=1.0),
) -> dict:
    """Return semantic code duplication candidates."""
    core_context: CoreContext = request.app.state.core_context
    return await get_analysis_duplicates(core_context, threshold=threshold)


@analysis_router.get("/common-knowledge")
# ID: 9e3f5a1b-2c4d-4e6f-7a8b-9c0d1e2f3ae9
async def analysis_common_knowledge(
    limit: int = Query(default=25, ge=1, le=200),
) -> dict:
    """Return DRY-violation candidates."""
    return await get_analysis_common_knowledge(limit=limit)


@analysis_router.get("/command-tree")
# ID: 0f4a6b2c-3d5e-4f7a-8b9c-0d1e2f3a4bf0
async def analysis_command_tree(request: Request) -> dict:
    """Return the introspected CLI command hierarchy."""
    core_context: CoreContext = request.app.state.core_context
    return get_analysis_command_tree(core_context)


@analysis_router.get("/test-targets")
# ID: 1a5b7c3d-4e6f-4a8b-9c0d-1e2f3a4b5ce1
async def analysis_test_targets(request: Request) -> dict:
    """Return SIMPLE / COMPLEX classification for in-scope source files."""
    core_context: CoreContext = request.app.state.core_context
    return get_analysis_test_targets(core_context)


# ---------- /components --------------------------------------------------


@components_router.get("")
# ID: 3b094d1e-e473-4044-9f46-16f6870f3946
async def components_list(
    filter_type: str | None = Query(default=None, alias="type"),
) -> dict:
    """Return the registered V2 component inventory across Mind/Body/Will."""
    return get_components_list(filter_type=filter_type)


# ---------- /search ------------------------------------------------------


@search_router.get("/capabilities")
# ID: 08ac8c57-ef92-4142-bf90-ba57bb0c6ce4
async def search_capabilities(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=200),
) -> dict:
    """Semantic capability search via the Will cognitive service."""
    core_context: CoreContext = request.app.state.core_context
    return await get_search_capabilities(core_context, q=q, limit=limit)
