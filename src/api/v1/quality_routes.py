# src/api/v1/quality_routes.py

"""
Quality API endpoints (ADR-055 Phase 2, D3).

The /quality namespace divides into two execution models:

* Synchronous (POST /quality/imports, POST /quality/body-ui) — fast
  inline checks. The route awaits the backend, shapes the ADR-055 D3
  response `{status, violations}`, returns 200. No fix_runs row.

* Asynchronous (POST /quality/lint, POST /quality/tests,
  POST /quality/system, POST /quality/gates) — subprocess-backed.
  The route INSERTs a pending row in core.fix_runs (kind='quality_check',
  fix_id=check_name), schedules execution on a background task, and
  returns 202 with the run_id and a poll href pointing at
  /v1/fix/runs/{id} — the /fix resource read endpoint serves
  quality_check rows by design (single resource table, ADR-055 D1).

CONSTITUTIONAL:
- Session access via api.dependencies.get_api_session /
  open_background_session only.
- CoreContext is read from request.app.state.core_context.
- body.* is reached through the will.governance.fix_runner facade —
  no direct imports here (architecture.api.no_body_bypass).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
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
    run_and_persist_quality,
    run_quality_body_ui,
    run_quality_imports,
    run_quality_policy_coverage,
)


logger = getLogger(__name__)


router = APIRouter(
    prefix="/quality",
    # F-40.1: internal — quality-gate dispatch (mypy/pytest/pip-audit/
    # ruff/radon/vulture) is CI-internal, not a sidecar concern.
    # Excluded from /v1/openapi.json per ADR-087.
    include_in_schema=False,
)


# ID: 3b42b16d-03d5-4114-bbda-75965bf614ad
class QualityTargetRequest(BaseModel):
    """Body for the two synchronous /quality endpoints."""

    target_files: list[str] | None = None


# ID: 5d78bfbd-f21b-4918-b6ab-aee0ffbad1d2
class QualityLintRequest(BaseModel):
    """Body for POST /quality/lint."""

    fix: bool = False
    requested_by: str = "api"


# ID: 22a0c461-1ed9-49e2-bf90-6012cbdfb1e8
class QualityTestsRequest(BaseModel):
    """Body for POST /quality/tests."""

    path: str | None = None
    requested_by: str = "api"


# ID: 378fa29d-1b53-4277-81ef-9536b7204d2e
class QualityAsyncRequest(BaseModel):
    """Body for POST /quality/system and POST /quality/gates."""

    requested_by: str = "api"


# ID: 66a524c0-02ea-4e56-acb8-80ded84e3966
async def _dispatch_quality(
    *,
    check: Literal["lint", "tests", "system", "gates"],
    params: dict,
    requested_by: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession,
) -> dict:
    """Shared body for the four async /quality endpoints.

    Inserts a pending fix_runs row (kind='quality_check', fix_id=check)
    and schedules run_and_persist_quality on a background task. The
    response href points at /fix/runs/{id} — that endpoint serves
    quality_check rows alongside atomic / flow / modularity rows.
    """
    core_context: CoreContext = request.app.state.core_context

    result = await session.execute(
        text(
            """
            INSERT INTO core.fix_runs
                (kind, fix_id, write, status, requested_by)
            VALUES ('quality_check', :check, FALSE, 'pending', :requested_by)
            RETURNING id
            """
        ),
        {"check": check, "requested_by": requested_by},
    )
    run_id: UUID = result.scalar_one()
    await session.commit()

    # ID: 6a26c22a-b5c9-4063-bcdc-f01077e9002d
    async def drive_quality() -> None:
        """Background task — owns its own session per ADR-053 lifecycle."""
        async for bg_session in open_background_session():
            await run_and_persist_quality(
                core_context,
                bg_session,
                run_id=run_id,
                check=check,
                params=params,
            )

    background_tasks.add_task(drive_quality)

    response.status_code = 202
    return {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/fix/runs/{run_id}",
    }


# ----------------------------------------------------------------------
# Synchronous endpoints
# ----------------------------------------------------------------------


@router.post("/imports")
# ID: 426c8ef0-3264-4e0d-9d6a-330bc46bbea3
async def quality_imports(
    payload: QualityTargetRequest = Body(default_factory=QualityTargetRequest),
) -> dict:
    """Run the import-resolution check inline. Returns {status, violations}."""
    return await run_quality_imports(payload.target_files)


@router.post("/body-ui")
# ID: b9aea824-c569-4243-9eaf-4fc55b895202
async def quality_body_ui(
    request: Request,
    payload: QualityTargetRequest = Body(default_factory=QualityTargetRequest),
) -> dict:
    """Run the Body-layer UI contract check inline. Returns {status, violations}."""
    core_context: CoreContext = request.app.state.core_context
    return await run_quality_body_ui(core_context, payload.target_files)


@router.post("/policy-coverage")
# ID: 7c1b5e8a-4f2d-49a6-b3e8-d1c4a2f6b9e0
async def quality_policy_coverage(request: Request) -> dict:
    """Run the constitutional policy-coverage audit inline.

    Returns the flattened PolicyCoverageReport: {report_id,
    generated_at_utc, repo_root, summary, records, exit_code}. Sync;
    no fix_runs row.
    """
    core_context: CoreContext = request.app.state.core_context
    return await run_quality_policy_coverage(core_context)


# ----------------------------------------------------------------------
# Asynchronous endpoints — fix_runs (kind='quality_check')
# ----------------------------------------------------------------------


@router.post("/lint")
# ID: d410a899-05c7-4ba4-a36e-1e3bb56623ee
async def quality_lint(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: QualityLintRequest = Body(default_factory=QualityLintRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch ruff lint (optionally with --fix). Async."""
    return await _dispatch_quality(
        check="lint",
        params={"fix": payload.fix},
        requested_by=payload.requested_by,
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


@router.post("/tests")
# ID: f29522c9-b43e-48ff-bd9e-ce93d88ffe09
async def quality_tests(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: QualityTestsRequest = Body(default_factory=QualityTestsRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch pytest, optionally scoped to a path. Async."""
    return await _dispatch_quality(
        check="tests",
        params={"path": payload.path},
        requested_by=payload.requested_by,
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


@router.post("/system")
# ID: 8cd84f9d-a9eb-4c17-bc5c-eef650da7e7e
async def quality_system(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: QualityAsyncRequest = Body(default_factory=QualityAsyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch the lint + tests bundle. Async."""
    return await _dispatch_quality(
        check="system",
        params={},
        requested_by=payload.requested_by,
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


@router.post("/gates")
# ID: c8876c66-40b1-4d55-b81d-dc9d91558ccb
async def quality_gates(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: QualityAsyncRequest = Body(default_factory=QualityAsyncRequest),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Dispatch the six-gate quality bundle (ruff/mypy/pytest/pip-audit/radon/vulture)."""
    return await _dispatch_quality(
        check="gates",
        params={},
        requested_by=payload.requested_by,
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )
