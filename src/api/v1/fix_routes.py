# src/api/v1/fix_routes.py

"""
Fix API endpoints (ADR-055 Phase 2, D2).

Endpoints in this module fall into three groups:

* Async dispatch — POST /fix/run/{fix_id}, POST /fix/all,
  POST /fix/modularity. Each validates an id against its registry,
  INSERTs a pending row in core.fix_runs, schedules execution on a
  background task, and returns 202 with the run_id and a poll href.

* Resource read — GET /fix/runs/{run_id} returns the persisted
  fix_runs row; missing → 404.

* Synchronous dispatch — GET /fix/commands and GET /actions read the
  registry inline. POST /fix/ir writes a YAML scaffold via FileHandler
  and returns the path; no resource row.

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- body.* is reached through the will.governance.fix_runner facade —
  no direct imports here (architecture.api.no_body_bypass).
"""

from __future__ import annotations

import json
from typing import Literal
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
from will.governance.fix_runner import (
    bootstrap_ir,
    list_action_definitions,
    list_registered_action_ids,
    list_registered_flow_ids,
    run_and_persist_fix,
    run_and_persist_flow,
    run_and_persist_modularity,
)


logger = getLogger(__name__)


FIX_CODE_FLOW_ID = "flow.fix_code"


router = APIRouter(prefix="/fix")
# Top-level router for GET /actions (ADR-055 D2 places it outside the
# /fix namespace; mounted alongside `router` in api/main.py).
actions_router = APIRouter()


# ID: 00691e83-00ae-4ca2-b3cb-de25b0070d02
class RunFixRequest(BaseModel):
    """Body for POST /fix/run/{fix_id}.

    Empty body is valid and equivalent to a default-constructed model
    (no target file restriction, dry-run).
    """

    target_files: list[str] | None = None
    write: bool = False
    requested_by: str = "api"


# ID: b0666d78-da54-4df4-810d-770ea3011eec
class RunFlowRequest(BaseModel):
    """Body for POST /fix/all and POST /fix/modularity."""

    write: bool = False
    requested_by: str = "api"


# ID: a3575778-f33a-4ed2-a92d-d29451e912dc
class RunIRRequest(BaseModel):
    """Body for POST /fix/ir."""

    kind: Literal["triage", "log"]


@router.post("/run/{fix_id}")
# ID: 4f1f7aa0-ad2c-4e49-8ab4-5712af1516e6
async def run_fix(
    fix_id: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: RunFixRequest = Body(default_factory=RunFixRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch an atomic fix action by id.

    Validates `fix_id` against the action registry — unknown ids return
    422 with the list of registered ids in the response body. Valid
    ids land a pending row in core.fix_runs and queue background
    execution via the will.governance.fix_runner facade.
    """
    registered = list_registered_action_ids()
    if fix_id not in registered:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Unknown fix_id: {fix_id}",
                "registered_count": len(registered),
            },
        )

    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.fix_runs
                (kind, fix_id, target_files, write, status, requested_by)
            VALUES ('atomic', :fix_id, cast(:target_files as jsonb),
                    :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "fix_id": fix_id,
            "target_files": (
                json.dumps(payload.target_files)
                if payload.target_files is not None
                else None
            ),
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: b33779c2-a2ff-4533-8e8e-6f0b4e8550e8
    async def drive_fix() -> None:
        """Background task — owns its own session per ADR-053 lifecycle."""
        async for bg_session in open_background_session():
            await run_and_persist_fix(
                core_context,
                bg_session,
                run_id=run_id,
                fix_id=fix_id,
                target_files=payload.target_files,
                write=payload.write,
            )

    background_tasks.add_task(drive_fix)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/fix/runs/{run_id}",
    }


# ID: bf32c06c-2caf-45be-8c83-6f8a3eaa857e
async def _dispatch_flow(
    *,
    flow_id: str,
    kind: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: RunFlowRequest,
    session: AsyncSession,
) -> dict:
    """Shared body for POST /fix/all and POST /fix/modularity.

    Validates flow_id against the flow registry, inserts a pending
    fix_runs row with the supplied `kind`, and schedules
    run_and_persist_flow on a background task.
    """
    registered = list_registered_flow_ids()
    if flow_id not in registered:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Unknown flow_id: {flow_id}",
                "registered_count": len(registered),
            },
        )

    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.fix_runs
                (kind, fix_id, write, status, requested_by)
            VALUES (:kind, :flow_id, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "kind": kind,
            "flow_id": flow_id,
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 4a5fef92-860d-4cd8-a670-cf24d9f3ec22
    async def drive_flow() -> None:
        """Background task — owns its own session per ADR-053 lifecycle."""
        async for bg_session in open_background_session():
            await run_and_persist_flow(
                core_context,
                bg_session,
                run_id=run_id,
                flow_id=flow_id,
                write=payload.write,
            )

    background_tasks.add_task(drive_flow)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/fix/runs/{run_id}",
    }


@router.post("/all")
# ID: ee17fca7-f08a-4792-beaf-e1f0006f0e74
async def run_fix_all(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: RunFlowRequest = Body(default_factory=RunFlowRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch the curated fix sequence (flow.fix_code). Kind='flow'."""
    return await _dispatch_flow(
        flow_id=FIX_CODE_FLOW_ID,
        kind="flow",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )


@router.post("/modularity")
# ID: e6c995f2-6eab-4613-97dd-722689161e2b
async def run_fix_modularity(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: RunFlowRequest = Body(default_factory=RunFlowRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch the modularity remediation cycle. Kind='modularity'.

    Backed by ModularityRemediationService — a Python-level workflow,
    not a Flow YAML — so there is no flow_id to validate at request
    time. The row carries fix_id=NULL and kind='modularity'.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.fix_runs
                (kind, fix_id, write, status, requested_by)
            VALUES ('modularity', NULL, :write, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {
            "write": payload.write,
            "requested_by": payload.requested_by,
        },
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: f0c530d1-f861-4b70-8358-e6e8b6ce30d2
    async def drive_modularity() -> None:
        """Background task — owns its own session per ADR-053 lifecycle."""
        async for bg_session in open_background_session():
            await run_and_persist_modularity(
                core_context,
                bg_session,
                run_id=run_id,
                write=payload.write,
            )

    background_tasks.add_task(drive_modularity)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/fix/runs/{run_id}",
    }


@router.post("/ir")
# ID: d638b36f-dfb4-4417-bba7-a180de2cf193
async def run_fix_ir(
    request: Request,
    payload: RunIRRequest = Body(...),
) -> dict:
    """Bootstrap an IR scaffold file synchronously.

    Returns the relative path that was written. Operation completes
    inline — no fix_runs row, no background task.
    """
    core_context: CoreContext = request.app.state.core_context
    try:
        path = bootstrap_ir(core_context, payload.kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"path": path}


@router.get("/commands")
# ID: e1dfec9d-5e9f-4aec-a96b-2bc1532360eb
async def list_fix_commands() -> dict:
    """Return metadata for registered fix-category atomic actions.

    Backs the CLI command discovery path; filtered to category=='fix'
    so the response is scoped to the /fix surface rather than the full
    action registry (see GET /actions for the unfiltered view).
    """
    commands = list_action_definitions(category="fix")
    return {"count": len(commands), "commands": commands}


@router.get("/runs/{run_id}")
# ID: 1a8efd3f-7107-4aaf-98cc-82f01a93a5cb
async def get_fix_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a persisted fix run by id, or 404 if unknown.

    The response shape matches ADR-055 D2: run_id, status, fix_id,
    kind, write, result, error. `result` is the JSONB payload written
    by the background task (ActionResult fields) and is null while the
    run is still pending or executing.
    """
    result = await session.execute(
        text(
            """
            SELECT id, kind, fix_id, target_files, write, status,
                   requested_by, requested_at, started_at, finished_at,
                   result, error
              FROM core.fix_runs
             WHERE id = :rid
            """
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fix run not found: {run_id}",
        )

    return {
        "run_id": str(row["id"]),
        "kind": row["kind"],
        "fix_id": row["fix_id"],
        "target_files": row["target_files"],
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


@actions_router.get("/actions")
# ID: 64f8b369-b83d-4caf-ab08-fc46984bcc44
async def list_actions() -> dict:
    """Return metadata for every registered atomic action.

    Unlike GET /fix/commands this is not filtered by category —
    consumers needing only the fix subset should call /fix/commands.
    """
    all_actions = list_action_definitions()
    return {"count": len(all_actions), "actions": all_actions}
