# src/api/v1/audit_routes.py

"""
Audit API endpoints (ADR-054 Phase 1, D1).

`POST /audit/runs` has two modes:

* `wait=false` (default) — fire-and-forget; inserts a pending row in
  core.audit_runs, returns the run_id with status 202, and drives the
  audit on a background task. Used by programmatic callers that don't
  need to block on the result.

* `wait=true` — synchronous; runs the audit inside the request
  handler and returns the full result (verdict, findings, stats,
  executed_rule_ids, auto_ignored) with status 200. Used by
  `core-admin code audit`. Audit duration is ~60s — clients must set
  a long HTTP timeout.

`GET /audit/runs/{id}` reads back the audit_runs row (verdict,
counts, timestamps). It does NOT return the finding list — see the
ADR-054 gap note below.

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- mind.* / shared.infrastructure.* are reached through the
  will.governance.audit_runner facade — no direct imports here.
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

from api.dependencies import get_api_session, open_background_session
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.audit_runner import run_and_persist_audit, run_sync_audit


logger = getLogger(__name__)


router = APIRouter(prefix="/audit")


# ID: b8443c8a-97ea-4011-8b99-f20e8d19e4eb
class CreateAuditRunRequest(BaseModel):
    """Body for POST /audit/runs.

    Empty body is valid and equivalent to a default-constructed model
    (full audit, async, no LLM-cache bypass).
    """

    rule_ids: list[str] = []
    policy_ids: list[str] = []
    files: list[str] = []
    force_llm: bool = False
    wait: bool = False
    source: str = "api"


@router.post("/runs")
# ID: 26d3745c-b1a3-419f-a521-06691b8a2c75
async def create_audit_run(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: CreateAuditRunRequest = Body(default_factory=CreateAuditRunRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Start a new audit run.

    See module docstring for the wait=true vs wait=false split.
    """
    core_context: CoreContext = request.app.state.core_context

    if payload.wait:
        # Synchronous — full result returned in-band (status 200).
        return await run_sync_audit(
            core_context,
            session,
            rule_ids=payload.rule_ids,
            policy_ids=payload.policy_ids,
            files=payload.files,
            force_llm=payload.force_llm,
            source=payload.source,
        )

    # Async — fire and forget (status 202). The pending row gives the
    # caller a run_id to poll GET /audit/runs/{id} for. See the
    # ADR-054 gap note on GET.
    response.status_code = 202
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
    """Return a persisted audit run by id, or 404 if unknown.

    ADR-054 GAP: ADR-054 verification criterion #2 calls for this
    endpoint to return the "full finding list" alongside the verdict
    and counts. Findings are not persisted per-run today — core.audit_runs
    stores counts only — so the response shape below is intentionally
    counts-only. Sync mode (POST /audit/runs with wait=true) is the
    surface that returns findings; the async-findings gap is tracked
    in #340.
    """
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
