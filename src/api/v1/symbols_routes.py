# src/api/v1/symbols_routes.py

"""Symbols audit routes — read-only diagnostic surface (ADR-146 D2).

Exposes:
- GET /symbols/unassigned  — public symbols with capability == 'unassigned'
- GET /symbols/drift       — drift summary from governed pipeline data

Mutation ops (fix.ids, fix.duplicate_ids, sync.db) dispatch through the
existing POST /fix/run/{fix_id} endpoint.

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- No direct DB imports; KnowledgeService accepts the injected session.
- No settings imports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/symbols", tags=["Symbols"])


@router.get("/unassigned", summary="List symbols with no capability assignment")
# ID: 26e5e000-bfec-408f-8216-af5ac41c8996
async def list_unassigned_symbols(
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return all public, non-test symbols that have capability == 'unassigned'.

    Mirrors the filter used by the CORE CLI's `symbols audit` check.
    Values from the knowledge graph view — no filesystem re-scan.
    """
    svc = KnowledgeService(session=session)
    graph = await svc.get_graph()
    symbols = graph.get("symbols") or {}

    unassigned = []
    for key, data in symbols.items():
        name = data.get("name")
        if name is None or name.startswith("_"):
            continue
        file_path = data.get("file_path", "")
        if "tests/" in file_path or "/test" in file_path:
            continue
        if data.get("capability") == "unassigned":
            unassigned.append({"key": key, **data})

    return {"unassigned": unassigned, "count": len(unassigned)}


@router.get("/drift", summary="Symbol drift summary from governed pipeline data")
# ID: 8bde40c7-3f6a-40bb-b8fe-57fe53a3d894
async def symbols_drift() -> dict:
    """Return symbol drift counters sourced from the governed pipeline.

    Reports anchor_violations (open purity.stable_id_anchor findings),
    pending_symbols (core.symbols rows pending classification), and
    last_sync_at (most recent DbSyncWorker heartbeat timestamp).

    Does not re-scan source — consumes governed pipeline output per ADR-143 D3.
    """
    from body.introspection.drift_service import run_drift_analysis_async

    return await run_drift_analysis_async()
