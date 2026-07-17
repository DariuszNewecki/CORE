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
counts, timestamps, status, findings list). Findings are denormalized
on `core.audit_runs.findings` (jsonb) — see the ADR-054 amendment.

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
    Query,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, open_background_session, require_governor
from api.v1.schemas import (
    AsyncDispatchResponse,
    AuditRunResponse,
    RemediationRunResponse,
)
from shared.context import CoreContext
from shared.logger import getLogger
from shared.pagination import decode_cursor, encode_cursor
from will.governance.audit_remediation_runner import (
    MODE_ALIASES,
    run_and_persist_audit_remediation,
)
from will.governance.audit_runner import run_and_persist_audit, run_sync_audit


logger = getLogger(__name__)


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/audit")

# ADR-132 D9 (#808): routes confirmed intentionally ungated, with rationale.
INTENTIONALLY_UNGATED: dict[str, str] = {
    "create_audit_run": (
        "Read-shaped: audit runs are analysis. Writes only to core.audit_runs "
        "tracking rows and disposable report artifacts (findings.json, "
        "evidence ledger) under reports/ — never src/, .intent/, or git. "
        "Contrast create_remediation_run (gated): applies fixes to src/ when "
        "write=true."
    ),
}


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


@router.post(
    "/runs",
    status_code=202,
    summary="Start an audit run",
    description=(
        "Start a constitutional audit run against the repo. With `wait=false` "
        "(default) returns 202 + a `run_id` to poll; the audit executes on a "
        "background task. With `wait=true` blocks and returns the full result "
        "(verdict + findings + stats) in-band (status 200). Audit duration is "
        "~60s; clients invoking `wait=true` must set a long HTTP timeout."
    ),
    responses={200: {"description": "Synchronous audit result (wait=true)"}},
)
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
        # Synchronous — full result returned in-band; override decorator default.
        response.status_code = 200
        return await run_sync_audit(
            core_context,
            session,
            rule_ids=payload.rule_ids,
            policy_ids=payload.policy_ids,
            files=payload.files,
            force_llm=payload.force_llm,
            source=payload.source,
        )

    # Async — fire and forget. The pending row gives the caller a run_id
    # to poll GET /audit/runs/{id} for. See the ADR-054 gap note on GET.
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

    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/audit/runs/{run_id}",
    }


@router.get(
    "/runs",
    summary="List audit runs",
    description=(
        "List recent audit runs newest-first (ordered by `run_id DESC`). "
        "`limit` defaults to 50 (max 500). Pass `after=<next_cursor>` from "
        "a previous response to advance the page. Returns `has_more` and "
        "`next_cursor` for keyset pagination."
    ),
)
# ID: 6bcc5bfb-79c3-4ee8-bf6a-e9a3b05e470e
async def list_audit_runs(
    limit: int = Query(default=50, ge=1, le=500),
    after: str | None = Query(
        default=None, description="Keyset cursor from a previous response."
    ),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """List audit runs, newest-first, with keyset pagination."""
    where_clause = ""
    params: dict = {"limit": limit + 1}
    if after is not None:
        try:
            _ts, cursor_key = decode_cursor(after)
            # run_id is UUID; cast to text for comparison
            where_clause = "WHERE CAST(run_id AS text) < :cursor_key"
            params["cursor_key"] = cursor_key
        except ValueError:
            pass  # malformed cursor — return from start

    result = await session.execute(
        text(
            f"""
            SELECT run_id, verdict, finding_count, blocking_count,
                   started_at, finished_at, status
              FROM core.audit_runs
            {where_clause}
             ORDER BY run_id DESC
             LIMIT :limit
            """
        ),
        params,
    )
    rows = result.mappings().all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_cursor(None, str(last["run_id"]))

    return {
        "count": len(page),
        "has_more": has_more,
        "next_cursor": next_cursor,
        "runs": [
            {
                "run_id": str(r["run_id"]),
                "verdict": r["verdict"],
                "finding_count": r["finding_count"],
                "blocking_count": r["blocking_count"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "finished_at": r["finished_at"].isoformat()
                if r["finished_at"]
                else None,
                "status": r["status"],
            }
            for r in page
        ],
    }


@router.get(
    "/runs/{run_id}",
    response_model=AuditRunResponse,
    summary="Fetch a persisted audit run",
    dependencies=[require_governor],
    description=(
        "Read back an audit run's persisted record by `run_id`: verdict + "
        "counts + timestamps + status + findings list. Returns 404 if the run "
        "doesn't exist. Findings are denormalized on `core.audit_runs.findings` "
        "per ADR-054 amendment; pre-amendment rows return an empty list."
    ),
)
# ID: 7c4903f0-e174-4e52-915d-54988fe40d22
async def get_audit_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted audit run by id, or 404 if unknown.

    Returns the full resource record: verdict + counts + timestamps +
    status + findings list. Findings are denormalized on
    `core.audit_runs.findings` (jsonb) per the ADR-054 amendment;
    pre-amendment rows return an empty list. Closes #340.
    """
    result = await session.execute(
        text(
            """
            SELECT run_id, verdict, finding_count, blocking_count,
                   started_at, finished_at, status, findings
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
        "findings": row["findings"] or [],
    }


# ID: 4b7c8d9e-0f1a-4b2c-3d4e-5f6a7b8c9d0e
class CreateRemediationRequest(BaseModel):
    """Body for POST /audit/remediations (ADR-057 D4).

    `audit_run_id` is the prior `core.audit_runs` row whose findings are
    to be remediated. `mode` is the aggressiveness selector — wire
    vocabulary 'safe' | 'medium' | 'all' (mapped onto RemediationMode at
    the facade). `write=false` is the dry-run default (ADR-014).
    """

    audit_run_id: UUID
    mode: str = "safe"
    write: bool = False
    requested_by: str = "api"


@router.post(
    "/remediations",
    status_code=202,
    response_model=AsyncDispatchResponse,
    dependencies=[require_governor],
    summary="Dispatch autonomous remediation",
    description=(
        "Trigger autonomous remediation of findings from a prior audit run "
        "(`audit_run_id`). `mode` selects aggressiveness — wire vocabulary "
        "is `safe` | `medium` | `all`. `write=false` is the dry-run default "
        "(ADR-014). Returns 202 + a `run_id` for the new remediation run; "
        "use `GET /v1/audit/remediations/{run_id}` to read the result. 422 "
        "if `mode` is outside the allowed vocabulary."
    ),
)
# ID: 5c8d9e0f-1a2b-4c3d-4e5f-6a7b8c9d0e1f
async def create_remediation_run(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: CreateRemediationRequest = Body(...),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch autonomous remediation of audit findings (ADR-057 D4).

    Validates `mode` against the wire vocabulary, INSERTs a pending row
    in core.audit_remediation_runs, and schedules background execution
    via will.governance.audit_remediation_runner. The audit_run_id FK
    is enforced at the DB layer — a missing-audit_run_id 404 surfaces
    only on read, not at dispatch.
    """
    if payload.mode not in MODE_ALIASES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown remediation mode: {payload.mode!r}. "
                f"Allowed: {sorted(MODE_ALIASES.keys())}"
            ),
        )

    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.audit_remediation_runs
                (audit_run_id, mode, write, status, requested_by)
            VALUES (:audit_run_id, :mode, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "audit_run_id": payload.audit_run_id,
            "mode": payload.mode,
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 6d9e0f1a-2b3c-4d4e-5f6a-7b8c9d0e1f2a
    async def drive_remediation() -> None:
        async for bg_session in open_background_session():
            await run_and_persist_audit_remediation(
                core_context,
                bg_session,
                run_id=run_id,
                mode=payload.mode,
                write=payload.write,
            )

    background_tasks.add_task(drive_remediation)

    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/audit/remediations/{run_id}",
    }


@router.get(
    "/remediations/{run_id}",
    response_model=RemediationRunResponse,
    summary="Fetch a remediation run",
    dependencies=[require_governor],
    description=(
        "Read back a remediation run's persisted record by `run_id`: mode, "
        "write flag, status, timestamps, result, and error if any. Returns "
        "404 if the run doesn't exist."
    ),
)
# ID: 7e0f1a2b-3c4d-4e5f-6a7b-8c9d0e1f2a3b
async def get_remediation_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted remediation run by id, or 404 if unknown."""
    result = await session.execute(
        text(
            """
            SELECT id, audit_run_id, mode, write, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.audit_remediation_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audit remediation run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "audit_run_id": (str(row["audit_run_id"]) if row["audit_run_id"] else None),
        "mode": row["mode"],
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
