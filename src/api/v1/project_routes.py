# src/api/v1/project_routes.py

"""Project management routes — capability-docs generation (ADR-146 D2).

Exposes:
- POST /project/docs — generate capability reference documentation

Sibling /project routes split off for modularity (modularity.needs_refactor,
#782): BYOR onboarding (POST /project/onboard, /onboard/promote) lives in
onboard_routes.py; Scout (POST /project/scout) in scout_routes.py.

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- CoreContext provided via request.app.state.core_context.
- body.introspection access is the composition-root pattern;
  architecture.api.no_body_bypass is [r].
- No settings imports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, require_governor
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/project", tags=["Project"])


# ID: 99f391a1-4bc9-4bad-898a-5038b5645f8e
class DocsRequest(BaseModel):
    output: str = "docs/10_CAPABILITY_REFERENCE.md"


@router.post(
    "/docs",
    dependencies=[require_governor],
    summary="Generate capability reference documentation",
)
# ID: 3891de91-00a6-4067-9702-4eef4159d27e
async def generate_docs(
    body: DocsRequest,
    request: Request,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Generate the canonical Capability Reference from the knowledge graph.

    Fetches public capabilities from core.knowledge_graph and writes
    docs/10_CAPABILITY_REFERENCE.md via FileHandler. The `output` parameter
    is accepted for forward compatibility; the current implementation writes
    to the fixed path docs/10_CAPABILITY_REFERENCE.md.
    """
    from body.introspection.generate_capability_docs import main as _gen_docs

    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    try:
        await _gen_docs(session=session, repo_root=repo_root)
    except Exception as exc:
        logger.error("generate_docs failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Doc generation failed: {exc}"
        ) from exc
    return {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}
