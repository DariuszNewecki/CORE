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

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, require_governor
from api.v1.schemas import LlmResourceAuthoringResponse
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.llm_resource_runner import (
    run_author_llm_resource,
    run_check_llm,
    run_setup_llm,
)


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
# ID: bb7691ac-7de0-4375-9960-f02c3c11cbf8
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


# ID: 6e1b8d4a-3f7c-4a2e-b9d5-8c4a1f7e3b6d
class SetupLlmRequest(BaseModel):
    """Body for POST /llm-resources/setup (#1374)."""

    api_url: str
    embedding_model: str
    chat_model: str
    locality: str = "local"
    embedding_api_url: str = ""
    embedding_locality: str = ""
    write: bool = False


@router.post("/setup", response_model=LlmResourceAuthoringResponse)
# ID: 2f8a5c1d-7b4e-4d9a-a3c6-5e1f9b7d2a4c
async def setup_llm(
    request: Request,
    payload: SetupLlmRequest = Body(...),
) -> LlmResourceAuthoringResponse:
    """Create the system_config row and the two setup model rows."""
    core_context: CoreContext = request.app.state.core_context
    result = await run_setup_llm(
        core_context,
        write=payload.write,
        api_url=payload.api_url,
        embedding_model=payload.embedding_model,
        chat_model=payload.chat_model,
        locality=payload.locality,
        embedding_api_url=payload.embedding_api_url,
        embedding_locality=payload.embedding_locality,
    )
    return LlmResourceAuthoringResponse(
        ok=result.ok, data=result.data, duration_sec=result.duration_sec
    )


@router.post("/check", response_model=LlmResourceAuthoringResponse)
# ID: 7d3c9f2e-1a6b-4e8d-9b5f-4a2e8c6d1f3b
async def check_llm(
    request: Request, session: AsyncSession = Depends(get_api_session)
) -> LlmResourceAuthoringResponse:
    """Call the embedding model and the chat model once each; writes nothing."""
    core_context: CoreContext = request.app.state.core_context
    data = await run_check_llm(core_context, session)
    return LlmResourceAuthoringResponse(
        ok=bool(data.get("ok")), data=data, duration_sec=0.0
    )
