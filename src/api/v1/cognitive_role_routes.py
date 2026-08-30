# src/api/v1/cognitive_role_routes.py
"""
Cognitive-role projection API endpoint (#821 Unit 2).

Single synchronous endpoint over the `project.cognitive_roles` atomic
action. Unlike sync_routes.py's async-dispatch+poll pattern (built for
full-repo audits that take real wall-clock time), this diffs/updates at
most a handful of core.cognitive_roles rows and returns inline — no
core.sync_runs-style tracking table is needed.

CONSTITUTIONAL:
- No direct database session import — CoreContext + ActionExecutor own
  their own session acquisition inside the atomic action.
- body.atomic.* reached through will.governance.cognitive_role_runner —
  no direct ActionExecutor import here.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from api.dependencies import require_governor
from api.v1.schemas import CognitiveRoleProjectionResponse
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.cognitive_role_runner import run_project_cognitive_roles


logger = getLogger(__name__)

ROUTER_EXPOSURE = "governor-only"
router = APIRouter(
    prefix="/cognitive-roles",
    # Operator/governance tooling, not part of the OEM API contract —
    # excluded from /v1/openapi.json, matching sync_routes.py's posture.
    include_in_schema=False,
    dependencies=[require_governor],
)


# ID: c4a8e2f6-1d9b-4a3e-8c7f-2b5d9a1e4f6c
class ProjectCognitiveRolesRequest(BaseModel):
    """Body for POST /cognitive-roles/project. write=False diffs only."""

    write: bool = False


@router.post("/project", response_model=CognitiveRoleProjectionResponse)
# ID: d5b9f3a7-2e0c-4b4f-9d8a-3c6e0b2f5a7d
async def project_cognitive_roles(
    request: Request,
    payload: ProjectCognitiveRolesRequest = Body(
        default_factory=ProjectCognitiveRolesRequest
    ),
) -> CognitiveRoleProjectionResponse:
    """Diff (write=False) or apply (write=True) the cognitive-role capability projection."""
    core_context: CoreContext = request.app.state.core_context
    result = await run_project_cognitive_roles(core_context, write=payload.write)
    return CognitiveRoleProjectionResponse(
        ok=result.ok,
        data=result.data,
        duration_sec=result.duration_sec,
    )
