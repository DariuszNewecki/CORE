# src/api/v1/audit_routes.py

"""
Audit API endpoints (ADR-054 Phase 1, D1).

POST /audit/runs creates a pending row in core.audit_runs, returns
the run_id with 202, and drives the audit on a background task.
GET /audit/runs/{id} reads back the row.

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- mind.* / shared.infrastructure.* are reached through the
  will.governance.audit_runner facade — no direct imports here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, open_background_session
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.audit_runner import run_and_persist_audit


logger = getLogger(__name__)


router = APIRouter(prefix="/audit")


@router.post("/runs", status_code=202)
# ID: 26d3745c-b1a3-419f-a521-06691b8a2c75
async def create_audit_run(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Start a new audit run.

    Inserts a pending row inline so the caller gets a run_id back
    immediately with 202, then drives the audit on a background task
    that updates the same row with verdict/counts when it completes.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.audit_runs
                (source, verdict, finding_count, blocking_count, status)
            VALUES ('api', 'pending', 0, 0, 'pending')
            RETURNING run_id
            """
        )
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 3042f075-2d01-4950-bae2-3a599b416c30
    async def drive_audit() -> None:
        """Background task — owns its own session per ADR-053 lifecycle."""
        async for bg_session in open_background_session():
            await run_and_persist_audit(core_context, bg_session, run_id=run_id)

    background_tasks.add_task(drive_audit)

    return {"run_id": str(run_id), "status": "pending"}


@router.get("/runs/{run_id}")
# ID: 7c4903f0-e174-4e52-915d-54988fe40d22
async def get_audit_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted audit run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT run_id, verdict, finding_count, blocking_count,
                   started_at, finished_at, status
              FROM core.audit_runs
             WHERE run_id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audit run not found: {run_id}",
        )

    return {
        "run_id": str(row["run_id"]),
        "verdict": row["verdict"],
        "finding_count": row["finding_count"],
        "blocking_count": row["blocking_count"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "finished_at": (row["finished_at"].isoformat() if row["finished_at"] else None),
        "status": row["status"],
    }
