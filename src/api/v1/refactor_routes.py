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

from api.dependencies import get_api_session, open_background_session
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


router = APIRouter(prefix="/refactor")


# ID: 3a7b9c5d-6e8f-4a0b-1c2d-3e4f5a6b7c8f
class RunAutonomousRequest(BaseModel):
    """Body for POST /refactor/autonomous.

    `goal` is forwarded as the natural-language goal to the A3 loop.
    `write=false` is the dry-run default (ADR-014 dev-phase discipline).
    """

    goal: str
    write: bool = False
    requested_by: str = "api"


# ---------- GET endpoints -------------------------------------------------


@router.get("/threshold")
# ID: 4b8c0d6e-7f9a-4b1c-2d3e-4f5a6b7c8d9a
async def refactor_threshold(request: Request) -> dict:
    """Return the constitutional modularity threshold."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return {"threshold": get_refactor_threshold(repo_root)}


@router.get("/score")
# ID: 5c9d1e7f-8a0b-4c2d-3e4f-5a6b7c8d9e0b
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


@router.get("/candidates")
# ID: 6d0e2f8a-9b1c-4d3e-4f5a-6b7c8d9e0f1c
async def refactor_candidates(
    request: Request,
    min_score: float | None = Query(default=None, ge=0.0, le=200.0),
    limit: int | None = Query(default=50, ge=1, le=500),
) -> dict:
    """Return files exceeding the modularity threshold, highest first."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return get_refactor_candidates(repo_root, min_score=min_score, limit=limit)


@router.get("/stats")
# ID: 7e1f3a9b-0c2d-4e4f-5a6b-7c8d9e0f1a2d
async def refactor_stats(request: Request) -> dict:
    """Return aggregate modularity-score distribution."""
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    return get_refactor_stats(repo_root)


# ---------- POST async autonomous ----------------------------------------


@router.post("/autonomous")
# ID: 8f2a4b0c-1d3e-4f5a-6b7c-8d9e0f1a2b3e
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

    # ID: 9a3b5c1d-2e4f-4a6b-7c8d-9e0f1a2b3c4f
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

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/refactor/runs/{run_id}",
    }


@router.get("/runs/{run_id}")
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
