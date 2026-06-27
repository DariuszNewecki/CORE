# src/api/v1/sync_routes.py

"""
Sync API endpoints (ADR-058 Phase 4, D2).

Five endpoints, all async-dispatch + poll:

* `POST /sync/knowledge-graph`  → sync_type='knowledge_graph'
* `POST /sync/vectors`      → sync_type='vectors'
* `POST /sync/code-vectors` → sync_type='code_vectors'
* `POST /sync/dev-sync`     → sync_type='dev_sync' (composite)
* `GET  /sync/runs/{run_id}` → poll persisted sync_runs row

All four POST paths share one `_dispatch_sync` body that INSERTs a
pending row in `core.sync_runs` and schedules the dispatch on a
background task via `will.governance.sync_runner`.

CONSTITUTIONAL:
- Session access via `api.dependencies.get_api_session` /
  `open_background_session` only.
- `CoreContext` read from `request.app.state.core_context`.
- `body.atomic.*` and `will.workflows.*` reached through the
  `will.governance.sync_runner` facade — no direct imports here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, open_background_session, require_role
from api.v1.schemas import AsyncDispatchResponse
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.sync_runner import (
    ALLOWED_SYNC_TYPES,
    run_and_persist_sync,
)


logger = getLogger(__name__)


router = APIRouter(
    prefix="/sync",
    # F-40.1: internal — knowledge-graph + vector sync is operator
    # scheduler concern (DbSyncWorker runs on a ~5-minute cadence),
    # not part of the OEM API contract. Excluded from /v1/openapi.json
    # per ADR-087.
    include_in_schema=False,
)


# ID: 6e3a0f8b-2d7c-4f5a-0431-f6789a0bcdef
class SyncRequest(BaseModel):
    """Body for the four POST /sync/* endpoints.

    `target` is an optional scope filter forwarded to the backend.
    Backends that don't honour it ignore it.

    `force` is a backend-specific re-run hint. Today only
    `sync.vectors_code` honours it (resets chunk_count on already-embedded
    artifacts so the embed loop re-processes them). Default False — no
    behaviour change for callers that don't pass it.
    """

    write: bool = False
    target: str | None = None
    requested_by: str = "api"
    force: bool = False


# ID: 7f4b1a9c-3e8d-4a6b-1542-07890ab12345
async def _dispatch_sync(
    *,
    sync_type: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: SyncRequest,
    session: AsyncSession,
) -> dict:
    """Shared body for the four POST /sync/* endpoints."""
    if sync_type not in ALLOWED_SYNC_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown sync_type: {sync_type!r}. "
                f"Allowed: {sorted(ALLOWED_SYNC_TYPES)}"
            ),
        )

    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.sync_runs
                (sync_type, write, target, status, requested_by)
            VALUES (:sync_type, :write, :target, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "sync_type": sync_type,
            "write": payload.write,
            "target": payload.target,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 8a5c2b0d-4f9e-4b7c-2653-189012345abc
    async def drive_sync() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_sync(
                core_context,
                bg_session,
                run_id=run_id,
                sync_type=sync_type,
                write=payload.write,
                target=payload.target,
                force=payload.force,
            )

    background_tasks.add_task(drive_sync)

    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/sync/runs/{run_id}",
    }


@router.post("/knowledge-graph", status_code=202, response_model=AsyncDispatchResponse)
# ID: 9b6d3c1e-5a0f-4c8d-3764-29a01234abcd
async def sync_knowledge_graph(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: SyncRequest = Body(default_factory=SyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch code-symbols → PostgreSQL knowledge graph sync."""
    return await _dispatch_sync(
        sync_type="knowledge_graph",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )


@router.post("/vectors", status_code=202, response_model=AsyncDispatchResponse)
# ID: 0c7e4d2f-6b1a-4d9e-4875-3ab12345bcde
async def sync_vectors(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: SyncRequest = Body(default_factory=SyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch constitutional vector sync (PG ↔ Qdrant)."""
    return await _dispatch_sync(
        sync_type="vectors",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )


@router.post("/code-vectors", status_code=202, response_model=AsyncDispatchResponse)
# ID: 1d8f5e3a-7c2b-4e0f-5986-4bc23456cdef
async def sync_code_vectors(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: SyncRequest = Body(default_factory=SyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch codebase symbol embedding via the worker pipeline."""
    return await _dispatch_sync(
        sync_type="code_vectors",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )


@router.post("/dev-sync", status_code=202, response_model=AsyncDispatchResponse)
# ID: 2e9a6f4b-8d3c-4f1a-6a97-5cd34567def0
async def sync_dev_sync(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: SyncRequest = Body(default_factory=SyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch the composite fix + knowledge-graph + vectors workflow."""
    return await _dispatch_sync(
        sync_type="dev_sync",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )


@router.get("/runs/{run_id}", dependencies=[require_role("platform_admin")])
# ID: 3f0b7a5c-9e4d-4a2b-7ba8-6de45678ef01
async def get_sync_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted sync run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT id, sync_type, write, target, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.sync_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sync run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "sync_type": row["sync_type"],
        "write": row["write"],
        "target": row["target"],
        "status": row["status"],
        "requested_by": row["requested_by"],
        "requested_at": (
            row["requested_at"].isoformat() if row["requested_at"] else None
        ),
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "finished_at": (row["finished_at"].isoformat() if row["finished_at"] else None),
        "result": row["result"],
        "error": row["error"],
    }
