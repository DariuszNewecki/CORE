# src/api/v1/knowledge_routes.py

"""
Knowledge API endpoints.

CONSTITUTIONAL FIX (architecture.api.no_direct_database_access):
Session dependency now routes through api.dependencies — the single
sanctioned provider for the API layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/knowledge")


@router.get(
    "/capabilities",
    summary="List known capabilities",
    description=(
        "Return the capability registry from the knowledge graph. Sidecar "
        "consumers (F-34 web dashboard) use this to render the capability "
        "tree and to anchor proposal/action views against the constitutional "
        "capability taxonomy."
    ),
)
# ID: 0016df93-d0e5-45b0-b5b8-8f4170de3d9d
async def list_capabilities(
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """
    Return known capabilities.

    Tests expect a 200 on GET /v1/knowledge/capabilities and a JSON object
    with a 'capabilities' key.
    """
    service = KnowledgeService(session=session)
    caps = await service.list_capabilities()
    return {"capabilities": caps}
