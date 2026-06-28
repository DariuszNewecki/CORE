# src/api/v1/integration_routes.py

"""
Integration API endpoint (ADR-054 Phase 1).

POST /v1/integrate stages, formats, lints, and commits the working
tree via will.lifecycle.integration_runner. Long-running but
synchronous from the caller's perspective — there is no run-id to
poll, so the CLI just awaits the response.

CONSTITUTIONAL:
- mind.* / body.* / shared.infrastructure.* are not imported here.
  All work is delegated through will.lifecycle.integration_runner.
- CoreContext comes from request.app.state.core_context.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.context import CoreContext
from shared.logger import getLogger
from will.lifecycle.integration_runner import run_integration


logger = getLogger(__name__)


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(
    prefix="/integrate",
    # F-40.1: internal — integration/build dispatch is CI-internal, not
    # part of the OEM API contract. Excluded from /v1/openapi.json per
    # ADR-087.
    include_in_schema=False,
)


# ID: fd724178-3586-48bb-a519-280de29821a3
class IntegrateRequest(BaseModel):
    """Body for POST /integrate."""

    commit_message: str


@router.post("")
# ID: 578732cb-c976-4577-a6ef-3024e24d9833
async def integrate(
    payload: IntegrateRequest,
    request: Request,
) -> dict:
    """Run the integration workflow (stage → format/lint → commit).

    Returns 200 on success. Translates a failed workflow into a 502
    so the CLI can render a clear error; the underlying exit_code is
    surfaced in the detail object.
    """
    core_context: CoreContext = request.app.state.core_context
    result = await run_integration(core_context, payload.commit_message)
    if not result["ok"]:
        raise HTTPException(
            status_code=502,
            detail=f"Integration workflow failed: {result.get('error', 'unknown error')}",
        )
    return result
