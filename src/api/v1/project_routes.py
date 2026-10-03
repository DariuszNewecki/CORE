# src/api/v1/project_routes.py

"""Project management routes — capability-docs generation (ADR-146 D2).

Exposes:
- POST /project/docs — generate capability reference documentation.
  DEPRECATED 2026-10-03 (ADR-087 D4): it writes CORE's own docs/ outside the
  proposal path; `core-admin docs generate` is the documentation generator.
  Removal waits for /v2/ (ADR-087 D5).

Sibling /project routes split off for modularity (modularity.needs_refactor,
#782): BYOR onboarding (POST /project/onboard, /onboard/promote) lives in
onboard_routes.py; Scout (POST /project/scout) in scout_routes.py.

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- CoreContext provided via request.app.state.core_context.
- The capability-docs generator (body.introspection) is injected from
  api.dependencies (CapabilityDocsDep); no Body import here.
- No settings imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CapabilityDocsDep, get_api_session, require_governor
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/project", tags=["Project"])

# ADR-087 D4 (amended 2026-10-03) / D5: deprecation signal for POST
# /project/docs. Deprecated when 2ec0b734 declared it; sunset six months on;
# removal only at /v2/.
DOCS_DEPRECATED_AT = datetime(2026, 10, 3, 11, 55, 13, tzinfo=UTC)
DOCS_SUNSET_AT = datetime(2027, 4, 3, tzinfo=UTC)
# RFC 9745 Structured Field Date; RFC 8594 HTTP-date.
DOCS_DEPRECATION_HEADER = f"@{int(DOCS_DEPRECATED_AT.timestamp())}"
DOCS_SUNSET_HEADER = format_datetime(DOCS_SUNSET_AT, usegmt=True)


# ID: 99f391a1-4bc9-4bad-898a-5038b5645f8e
class DocsRequest(BaseModel):
    """
    Pydantic model declaring the target output path for generated API reference documentation.

    Args:
        output: Filesystem or repository-relative path where the documentation
            will be written, defaulting to the capabilities reference file.
    """

    output: str = "docs/10_CAPABILITY_REFERENCE.md"


@router.post(
    "/docs",
    dependencies=[require_governor],
    summary="Generate capability reference documentation (deprecated)",
    deprecated=True,
)
# ID: 3891de91-00a6-4067-9702-4eef4159d27e
async def generate_docs(
    body: DocsRequest,
    request: Request,
    response: Response,
    generate_docs_fn: CapabilityDocsDep,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Generate the canonical Capability Reference from the knowledge graph.

    Fetches public capabilities from core.knowledge_graph and writes
    docs/10_CAPABILITY_REFERENCE.md via FileHandler. The `output` parameter
    is accepted for forward compatibility; the current implementation writes
    to the fixed path docs/10_CAPABILITY_REFERENCE.md.
    """
    response.headers["Deprecation"] = DOCS_DEPRECATION_HEADER
    response.headers["Sunset"] = DOCS_SUNSET_HEADER
    core_context: CoreContext = request.app.state.core_context
    repo_root = core_context.git_service.repo_path
    try:
        await generate_docs_fn(session=session, repo_root=repo_root)
    except Exception as exc:
        logger.error("generate_docs failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Doc generation failed: {exc}"
        ) from exc
    return {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}
