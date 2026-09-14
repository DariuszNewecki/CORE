# src/api/v1/refactor_routes.py

"""
Refactor API endpoints (ADR-057 Phase 3, D2).

Two endpoint groups:

* Read-only queries — GET /refactor/score, /refactor/candidates,
  /refactor/stats, /refactor/threshold. Each returns synchronously.

* Async dispatch — POST /refactor/autonomous. Inserts a pending row in
  core.refactor_runs, schedules a background task on the
  will.governance.refactor_runner facade, returns 202 with run_id +
  poll href. GET /refactor/runs/{run_id} reads back the persisted row.

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- mind.* / will.autonomy.* are reached through the
  will.governance.refactor_runner facade — no direct imports here
  (architecture.api.no_body_bypass).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, open_background_session, require_governor
from api.v1.schemas import AsyncDispatchResponse
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.refactor_runner import (
    get_refactor_candidates,
    get_refactor_score,
    get_refactor_stats,
    get_refactor_threshold,
    run_and_persist_refactor_autonomous,
)


logger = getLogger(__name__)


ROUTER_EXPOSURE = "governor-only"
router = APIRouter(prefix="/refactor", dependencies=[require_governor])


# ID: 10a6a535-f31e-432b-8766-afb624b98fed
class RunAutonomousRequest(BaseModel):
    """Body for POST /refactor/autonomous.

    `goal` is forwarded as the natural-language goal to the A3 loop.
    `write=false` is the dry-run default (ADR-014 dev-phase discipline).
    """

    goal: str
    write: bool = False
    requested_by: str = "api"


# ---------- GET endpoints -------------------------------------------------


@router.get(
    "/threshold",
    summary="Constitutional modularity threshold",
    description=(
        "Return the constitutional modularity score threshold — files "
        "scoring above this are refactor candidates. Sidecar configuration "
        "surface."
    ),
)
# ID: 95edda5a-8c24-4bd0-8bfb-f17c8e19c6db
async def refactor_threshold(request: Request) -> dict:
    """Return the constitutional modularity threshold."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return {"threshold": get_refactor_threshold(repo_root)}


@router.get(
    "/score",
    summary="Per-file modularity score",
    description=(
        "Return the per-file modularity score for `file` (relative path). "
        "Returns 404 if the file is unknown / missing; analyzable files "
        "return the full details payload from the modularity engine."
    ),
)
# ID: 320944d1-57dc-46c2-ab33-052a6adde374
async def refactor_score(
    request: Request,
    file: str = Query(..., min_length=1),
) -> dict:
    """Return the per-file modularity score for `file` (relative path).

    Unknown / missing files resolve to 404; analyzable files return the
    full details payload from the modularity engine.
    """
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    payload = get_refactor_score(repo_root, file)
    if not payload["found"]:
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    return payload


@router.get(
    "/candidates",
    summary="Refactor candidates ranked by score",
    description=(
        "Return files exceeding the modularity threshold, highest score "
        "first. `min_score` filters to files at or above the given score "
        "(0-200); `limit` caps results (default 50, max 500). F-34 "
        "dashboards use this as an actionable refactor backlog view."
    ),
)
# ID: 3240977c-3a90-4415-aa75-72c4e0d709b6
async def refactor_candidates(
    request: Request,
    min_score: float | None = Query(default=None, ge=0.0, le=200.0),
    limit: int | None = Query(default=50, ge=1, le=500),
) -> dict:
    """Return files exceeding the modularity threshold, highest first."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return get_refactor_candidates(repo_root, min_score=min_score, limit=limit)


@router.get(
    "/stats",
    summary="Modularity-score distribution",
    description=(
        "Return the aggregate modularity-score distribution across the "
        "codebase — histogram + percentile summary used for trend analysis "
        "and dashboard rendering."
    ),
)
# ID: 080a6007-ff5f-4ebc-9b37-09f342c8ca2d
async def refactor_stats(request: Request) -> dict:
    """Return aggregate modularity-score distribution."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return get_refactor_stats(repo_root)


# ---------- POST async autonomous ----------------------------------------


@router.post(
    "/autonomous",
    status_code=202,
    response_model=AsyncDispatchResponse,
    # F-40.1: internal — dispatches the A3 autonomous refactor cycle.
    # Autonomy surface, not a sidecar concern. Excluded from
    # /v1/openapi.json per ADR-087.
    include_in_schema=False,
)
# ID: b888a38e-c4f3-460f-9383-269840edccd4
async def run_refactor_autonomous(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: RunAutonomousRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Trigger the A3 autonomous refactor cycle.

    Inserts a pending row in core.refactor_runs and queues background
    execution. The cycle's proposals land on core.autonomous_proposals;
    refactor_runs.result holds the captured proposal_ids.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.refactor_runs
                (goal, write, status, requested_by)
            VALUES (:goal, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "goal": payload.goal,
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: ee5dfb3f-4fc4-4371-908e-4911fc34cab7
    async def drive_autonomous() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_refactor_autonomous(
                core_context,
                bg_session,
                run_id=run_id,
                goal=payload.goal,
                write=payload.write,
            )

    background_tasks.add_task(drive_autonomous)

    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/refactor/runs/{run_id}",
    }


@router.get(
    "/runs/{run_id}",
    summary="Fetch a persisted refactor run",
    description=(
        "Read back a refactor run's persisted record by `run_id`: status, "
        "timestamps, captured proposal_ids in `result`, error. Returns "
        "404 if no run exists with that id."
    ),
)
# ID: 0b4c6d2e-3f5a-4b7c-8d9e-0f1a2b3c4d50
async def get_refactor_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted refactor run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT id, goal, write, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.refactor_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Refactor run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "goal": row["goal"],
        "write": row["write"],
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
