# src/api/v1/coverage_routes.py

"""
Coverage API endpoints (ADR-057 Phase 3, D1).

Three endpoint groups:

* Read-only queries — GET /coverage/check, /coverage/report (latest
  persisted run), /coverage/targets, /coverage/gaps, /coverage/history,
  /coverage/methods. Each returns a synchronous JSON payload.

* Async dispatch — POST /coverage/reports (#608 fix: fresh pytest run
  off the request thread), POST /coverage/generate, POST
  /coverage/generate:batch. Each inserts a pending row in
  core.coverage_runs, schedules a background task on the
  will.governance.coverage_runner facade, and returns 202 with the
  run_id + poll href.

* Resource read — GET /coverage/runs/{run_id}.

* Synchronous dispatch — POST /tests/interactive. Returns the result
  inline (200) — no coverage_runs row, no background task.

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- body.* / mind.* are reached through the
  will.governance.coverage_runner facade — no direct imports here
  (architecture.api.no_body_bypass).
"""

from __future__ import annotations

from typing import Literal
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
from will.governance.coverage_runner import (
    get_coverage_check,
    get_coverage_gaps,
    get_coverage_history,
    get_coverage_methods,
    get_coverage_targets,
    get_latest_coverage_report,
    run_and_persist_coverage_batch,
    run_and_persist_coverage_generation,
    run_and_persist_coverage_report,
    run_tests_interactive,
)


logger = getLogger(__name__)


router = APIRouter(prefix="/coverage")
# /tests/interactive lives outside the /coverage namespace per ADR-057
# D5 (the endpoint produces a one-shot interactive session response).
tests_router = APIRouter(prefix="/tests")


# ID: 8d2e4f0a-1b3c-4d5e-6f7a-8b9c0d1e2f30
class GenerateRequest(BaseModel):
    """Body for POST /coverage/generate."""

    target_file: str
    write: bool = False
    requested_by: str = "api"


# ID: 9e3f5a1b-2c4d-4e6f-7a8b-9c0d1e2f3a41
class GenerateBatchRequest(BaseModel):
    """Body for POST /coverage/generate:batch.

    `priority` ∈ {'high', 'all'} per ADR-057 D1. 'high' raises the target
    coverage; 'all' uses the default constitutional target.
    """

    priority: str = "all"
    write: bool = False
    requested_by: str = "api"


# ID: 0f4a6b2c-3d5e-4f7a-8b9c-0d1e2f3a4b52
class InteractiveTestsRequest(BaseModel):
    """Body for POST /tests/interactive."""

    target_file: str | None = None


# ID: 5e9f7c3d-4a6b-5e8f-9c0d-1e2f3a4b5c63
class ReportRequest(BaseModel):
    """Body for POST /coverage/reports.

    Triggers a pytest coverage run as a background job (#608 fix —
    moves the 30-60s pytest off the request thread). `format` selects
    text vs html output; `show_missing` toggles per-module missing-lines
    reporting (text format only).
    """

    format: Literal["text", "html"] = "text"
    show_missing: bool = False
    requested_by: str = "api"


# ---------- GET endpoints -------------------------------------------------


@router.get(
    "/check",
    summary="Constitutional coverage compliance check",
    description=(
        "Run the constitutional coverage compliance check — pass/fail "
        "verdict against the configured coverage targets. F-45 (hosted "
        "findings) renders this alongside audit findings for the same "
        "PR snapshot."
    ),
)
# ID: 1a5b7c3d-4e6f-4a8b-9c0d-1e2f3a4b5c63
async def coverage_check(request: Request) -> dict:
    """Run the constitutional coverage compliance check."""
    core_context: CoreContext = request.app.state.core_context
    return await get_coverage_check(core_context)


@router.get(
    "/report",
    summary="Latest pytest coverage report",
    description=(
        "Return the most recently completed pytest coverage report "
        "from `core.coverage_runs`. `format=text` (default) returns the "
        "latest text-format run; `format=html` returns the latest "
        "html-format run. 404 with a hint to POST /v1/coverage/reports "
        "if no completed report-run of the requested format exists yet. "
        "GET no longer runs pytest inline (closes #608) — POST "
        "/v1/coverage/reports kicks off a fresh run as a background task."
    ),
)
# ID: 2b6c8d4e-5f7a-4b9c-0d1e-2f3a4b5c6d74
async def coverage_report(
    format: Literal["text", "html"] = Query(default="text"),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return the latest completed coverage report of the requested format.

    Reads from `core.coverage_runs` where `target_file IS NULL AND
    batch_priority IS NULL` (the report-run discriminator) and
    `status='completed'`. Most recent finished_at wins.

    Prior behavior (running pytest inline on every GET) caused #608:
    the 30-60s pytest run starved the single uvicorn worker and
    cascaded request stalls onto every other endpoint. ADR-101's
    cousin principle for HTTP: GETs are cheap reads, never long jobs.
    Use POST /v1/coverage/reports to request a fresh run.
    """
    latest = await get_latest_coverage_report(session, format=format)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No completed coverage report of format={format!r} exists "
                f"yet. POST /v1/coverage/reports to request a fresh run, "
                f"then poll GET /v1/coverage/runs/{{run_id}} for the result."
            ),
        )
    return latest


@router.post(
    "/reports",
    # F-40.1: internal — triggers a pytest coverage run via the
    # autonomy loop. Not a sidecar consumer surface. Excluded from
    # /v1/openapi.json per ADR-087.
    include_in_schema=False,
)
# ID: 3c7d9e5f-6a8b-7c0d-1e2f-3a4b5c6d7e96
async def request_coverage_report(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: ReportRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch a fresh pytest coverage run as a background job (#608 fix).

    Inserts a pending row in `core.coverage_runs` with `target_file`
    and `batch_priority` both NULL (the report-run discriminator) and
    queues the pytest execution via
    `will.governance.coverage_runner.run_and_persist_coverage_report`.
    Returns 202 + run_id + href; poll `GET /v1/coverage/runs/{run_id}`
    for status and result.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.coverage_runs
                (target_file, batch_priority, write, status, requested_by)
            VALUES (NULL, NULL, false, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {"requested_by": payload.requested_by},
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 4d8e0f6a-7b9c-8d1e-2f3a-4b5c6d7e8f97
    async def drive_report() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_coverage_report(
                core_context,
                bg_session,
                run_id=run_id,
                format=payload.format,
                show_missing=payload.show_missing,
            )

    background_tasks.add_task(drive_report)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/coverage/runs/{run_id}",
    }


@router.get(
    "/targets",
    summary="Coverage targets",
    description=(
        "Return the constitutional coverage targets — module-level thresholds "
        "the audit gate enforces. Sidecar configuration surface."
    ),
)
# ID: 3c7d9e5f-6a8b-4c0d-1e2f-3a4b5c6d7e85
def coverage_targets(request: Request) -> dict:
    """Return the constitutional coverage targets.

    `def` not `async def` (#608 sibling fix): `get_coverage_targets` is
    a synchronous IntentRepository read. FastAPI auto-thread-pools `def`
    handlers, so the event loop stays free during the read instead of
    blocking under an `async def` shell.
    """
    core_context: CoreContext = request.app.state.core_context
    return get_coverage_targets(core_context)


@router.get(
    "/gaps",
    summary="Coverage gaps ranked by deficit",
    description=(
        "Return modules ranked by coverage deficit below `threshold` "
        "(default 75.0, range 0-100). `limit` caps results (default 20, "
        "max 200). F-34 dashboards use this as an actionable surface for "
        "operators to triage test debt."
    ),
)
# ID: 4d8e0f6a-7b9c-4d1e-2f3a-4b5c6d7e8f96
def coverage_gaps(
    request: Request,
    threshold: float = Query(default=75.0, ge=0.0, le=100.0),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    """Return modules ranked by coverage deficit below `threshold`.

    `def` not `async def` (#610 — last `/v1/coverage` async-def-with-sync-body
    holdout after #608's cascade fix): `get_coverage_gaps` wraps
    `CoverageAnalyzer.get_module_coverage()` which is synchronous. FastAPI
    auto-thread-pools `def` handlers, so the event loop stays free during
    the read instead of blocking under an `async def` shell.
    """
    core_context: CoreContext = request.app.state.core_context
    return get_coverage_gaps(core_context, threshold=threshold, limit=limit)


@router.get(
    "/history",
    summary="Coverage history",
    description=(
        "Return recent coverage measurements (newest first). `limit` "
        "defaults to 30, max 500. F-20-adjacent — surfaces coverage "
        "trajectory alongside the convergence metric."
    ),
)
# ID: 5e9f1a7b-8c0d-4e2f-3a4b-5c6d7e8f9a07
def coverage_history(
    request: Request,
    limit: int = Query(default=30, ge=1, le=500),
) -> dict:
    """Return recent coverage measurements.

    `def` not `async def` (#608 sibling fix): `get_coverage_history` is
    a synchronous filesystem read of `coverage_history.json`. FastAPI
    auto-thread-pools `def` handlers so the event loop stays free.
    """
    core_context: CoreContext = request.app.state.core_context
    return get_coverage_history(core_context, limit=limit)


@router.get(
    "/methods",
    # F-40.1: internal — baseline-vs-adaptive method comparison is
    # CORE-internal autonomy concern; sidecars don't care. Excluded
    # from /v1/openapi.json per ADR-087.
    include_in_schema=False,
)
# ID: 6f0a2b8c-9d1e-4f3a-4b5c-6d7e8f9a0b18
def coverage_methods(request: Request) -> dict:
    """Return the legacy-vs-adaptive coverage method comparison.

    `def` not `async def` (#608 sibling fix): `get_coverage_methods` is
    a synchronous read. FastAPI auto-thread-pools `def` handlers so the
    event loop stays free.
    """
    core_context: CoreContext = request.app.state.core_context
    return get_coverage_methods(core_context)


# ---------- POST async generation ----------------------------------------


@router.post(
    "/generate",
    # F-40.1: internal — triggers adaptive test generation via the
    # autonomy loop. Not a sidecar consumer surface. Excluded from
    # /v1/openapi.json per ADR-087.
    include_in_schema=False,
)
# ID: 7a1b3c9d-0e2f-4a4b-5c6d-7e8f9a0b1c29
async def generate_coverage(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: GenerateRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch adaptive test generation for a single file.

    Inserts a pending row in core.coverage_runs and queues background
    execution via will.governance.coverage_runner.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.coverage_runs
                (target_file, batch_priority, write, status, requested_by)
            VALUES (:target_file, NULL, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "target_file": payload.target_file,
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 8b2c4d0e-1f3a-4b5c-6d7e-8f9a0b1c2d3a
    async def drive_generate() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_coverage_generation(
                core_context,
                bg_session,
                run_id=run_id,
                target_file=payload.target_file,
                write=payload.write,
            )

    background_tasks.add_task(drive_generate)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/coverage/runs/{run_id}",
    }


@router.post(
    "/generate:batch",
    # F-40.1: internal — batch variant of /generate; same autonomy-loop
    # concern. Excluded from /v1/openapi.json per ADR-087.
    include_in_schema=False,
)
# ID: 9c3d5e1f-2a4b-4c6d-7e8f-9a0b1c2d3e4b
async def generate_coverage_batch(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: GenerateBatchRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch prioritised batch adaptive test generation."""
    if payload.priority not in {"high", "all"}:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Unknown priority: {payload.priority}",
                "allowed": ["high", "all"],
            },
        )

    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.coverage_runs
                (target_file, batch_priority, write, status, requested_by)
            VALUES (NULL, :priority, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "priority": payload.priority,
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 0d4e6f2a-3b5c-4d7e-8f9a-0b1c2d3e4f5c
    async def drive_batch() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_coverage_batch(
                core_context,
                bg_session,
                run_id=run_id,
                batch_priority=payload.priority,
                write=payload.write,
            )

    background_tasks.add_task(drive_batch)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/coverage/runs/{run_id}",
    }


# ---------- POST sync interactive ----------------------------------------


@tests_router.post(
    "/interactive",
    # F-40.1: internal — interactive test-shape dispatch is autonomy
    # surface, not a sidecar concern. Excluded from /v1/openapi.json
    # per ADR-087.
    include_in_schema=False,
)
# ID: 1e5f7a3b-4c6d-4e8f-9a0b-1c2d3e4f5a6d
async def interactive_tests(
    request: Request,
    payload: InteractiveTestsRequest = Body(default_factory=InteractiveTestsRequest),
) -> dict:
    """Run interactive adaptive test generation synchronously.

    No resource row. Returns the result dict inline with 200.
    """
    core_context: CoreContext = request.app.state.core_context
    return await run_tests_interactive(core_context, target_file=payload.target_file)


# ---------- GET resource read --------------------------------------------


@router.get(
    "/runs/{run_id}",
    summary="Fetch a persisted coverage run",
    description=(
        "Read back a coverage run's persisted record by `run_id`: status, "
        "timestamps, result payload, error. Returns 404 if no run exists "
        "with that id."
    ),
)
# ID: 2f6a8b4c-5d7e-4f9a-0b1c-2d3e4f5a6b7e
async def get_coverage_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted coverage run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT id, target_file, batch_priority, write, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.coverage_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Coverage run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "target_file": row["target_file"],
        "batch_priority": row["batch_priority"],
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
