# src/api/v1/llm_resource_routes.py
"""
llm_resources authoring API endpoint (#821 Unit 3).

Single synchronous endpoint over the `author.llm_resource` atomic action.
Validates or persists at most one core.llm_resources row and returns
inline — no core.sync_runs-style tracking table is needed.

CONSTITUTIONAL:
- No direct database session import — CoreContext + ActionExecutor own
  their own session acquisition inside the atomic action.
- body.atomic.* reached through will.governance.llm_resource_runner —
  no direct ActionExecutor import here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from api.dependencies import require_governor
from api.v1.schemas import LlmResourceAuthoringResponse
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.llm_resource_runner import run_author_llm_resource


logger = getLogger(__name__)

ROUTER_EXPOSURE = "governor-only"
router = APIRouter(
    prefix="/llm-resources",
    # Operator/governance tooling, not part of the OEM API contract —
    # excluded from /v1/openapi.json, matching cognitive_role_routes.py's
    # posture.
    include_in_schema=False,
    dependencies=[require_governor],
)


# ID: 4a8d2f6b-0e3c-4a7f-b1c5-9e3a7c1f5b9d
class AuthorLlmResourceRequest(BaseModel):
    """Body for POST /llm-resources/author.

    write=False validates `definition` without persisting.
    """

    definition: dict[str, Any]
    write: bool = False


@router.post("/author", response_model=LlmResourceAuthoringResponse)
# ID: 5b9e3a7c-1f4d-4b8e-c2d6-0f4b8d2e6a0c
async def author_llm_resource(
    request: Request,
    payload: AuthorLlmResourceRequest = Body(...),
) -> LlmResourceAuthoringResponse:
    """Validate (write=False) or validate-and-persist (write=True) an llm_resources row."""
    core_context: CoreContext = request.app.state.core_context
    result = await run_author_llm_resource(
        core_context, write=payload.write, definition=payload.definition
    )
    return LlmResourceAuthoringResponse(
        ok=result.ok,
        data=result.data,
        duration_sec=result.duration_sec,
    )
