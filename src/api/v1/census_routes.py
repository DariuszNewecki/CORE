# src/api/v1/census_routes.py

"""
Census API endpoints (ADR-058 Phase 4, D1).

Three endpoint groups:

* Async dispatch — `POST /census/runs` inserts a pending row in
  `core.census_runs`, schedules a background task on the
  `will.governance.census_runner` facade, returns 202 with run_id +
  poll href.

* Resource read — `GET /census/runs/{run_id}` returns the persisted row.

* Synchronous baseline + diff — `POST /census/baselines/{name}`,
  `GET /census/baselines`, `GET /census/diff` operate against the
  on-disk baseline registry and snapshot history.

CONSTITUTIONAL:
- Session access via `api.dependencies.get_api_session` /
  `open_background_session` only.
- `CoreContext` read from `request.app.state.core_context`.
- `body.services.cim.*` reached through the
  `will.governance.census_runner` facade — no direct imports here
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
from will.governance.census_runner import (
    create_baseline,
    get_diff,
    list_baselines,
    run_and_persist_census,
)


logger = getLogger(__name__)


router = APIRouter(prefix="/census")


# ID: 8c5e2d0f-4b9a-4d7e-ecbe-7f8901ab23cd
class CreateCensusRunRequest(BaseModel):
    """Body for POST /census/runs."""

    snapshot: bool = False
    requested_by: str = "api"


# ID: 9d6f3e1a-5c0b-4e8f-fdcf-89012ab34d5e
class CreateBaselineRequest(BaseModel):
    """Body for POST /census/baselines/{name}.

    `snapshot_file` is optional — when omitted the most recent snapshot
    is used. The handler maps the missing-snapshot case to 422.
    """

    snapshot_file: str | None = None


@router.post(
    "/runs",
    summary="Dispatch a structural census",
    description=(
        "Trigger a CIM-0 structural census snapshot of the constitution and "
        "codebase. Returns 202 + a `run_id` to poll. F-20 (Convergence "
        "dashboard) ingests these snapshots over time to render the "
        "finding-rate vs resolution-rate trajectory."
    ),
)
# ID: 0e7a4f2b-6d1c-4f9a-aedb-90123ab456f7
async def create_census_run(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: CreateCensusRunRequest = Body(default_factory=CreateCensusRunRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch a CIM-0 structural census."""
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.census_runs
                (snapshot, status, requested_by)
            VALUES (:snapshot, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "snapshot": payload.snapshot,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 1f8b5a3c-7e2d-4a0b-bfec-a1234bc567f8
    async def drive_census() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_census(
                core_context,
                bg_session,
                run_id=run_id,
                snapshot=payload.snapshot,
            )

    background_tasks.add_task(drive_census)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/census/runs/{run_id}",
    }


@router.get(
    "/runs/{run_id}",
    summary="Fetch a persisted census run",
    description=(
        "Read back a census run's persisted record by `run_id`: snapshot, "
        "baseline_name, status, timestamps, result, error. Returns 404 if "
        "the run doesn't exist."
    ),
)
# ID: 2a9c6b4d-8f3e-4b1c-c0fd-b2345cd6789a
async def get_census_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted census run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT id, snapshot, baseline_name, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.census_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Census run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "snapshot": row["snapshot"],
        "baseline_name": row["baseline_name"],
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


@router.post(
    "/baselines/{name}",
    summary="Create a named census baseline",
    description=(
        "Promote a census snapshot to a named baseline. F-20 dashboards use "
        "baselines as reference points for the convergence trajectory. "
        "`snapshot_file` is optional; when omitted, the most recent snapshot "
        "is used. Returns 422 if no usable snapshot exists."
    ),
)
# ID: 3b0d7c5e-9a4f-4c2d-d10e-c3456de789ab
async def create_census_baseline(
    request: Request,
    name: str,
    payload: CreateBaselineRequest = Body(default_factory=CreateBaselineRequest),
) -> dict:
    """Create a named baseline from a prior census snapshot."""
    core_context: CoreContext = request.app.state.core_context
    try:
        baseline = create_baseline(
            core_context, name=name, snapshot_file=payload.snapshot_file
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"baseline": baseline}


@router.get(
    "/baselines",
    summary="List census baselines",
    description="Return all named baselines (newest first).",
)
# ID: 4c1e8d6f-0b5a-4d3e-e21f-d4567ef89abc
async def list_census_baselines(request: Request) -> dict:
    """Return all named baselines (newest first)."""
    core_context: CoreContext = request.app.state.core_context
    return list_baselines(core_context)


@router.get(
    "/diff",
    summary="Compare current state to a baseline",
    description=(
        "Diff the current census state against a baseline. The optional "
        "`baseline` query param selects which named baseline to compare "
        "against; omit to use the default baseline if configured. Returns "
        "the structured delta consumed by F-20 dashboards."
    ),
)
# ID: 5d2f9e7a-1c6b-4e4f-f320-e5678f0abcde
async def census_diff(
    request: Request,
    baseline: str | None = Query(default=None),
) -> dict:
    """Diff the latest snapshot against a baseline (or the previous one)."""
    core_context: CoreContext = request.app.state.core_context
    return get_diff(core_context, baseline=baseline)
