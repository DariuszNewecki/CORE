# src/api/v1/knowledge_routes.py

"""
Knowledge API endpoints.

CONSTITUTIONAL FIX: Uses service_registry.session() instead of direct get_session
to comply with architecture.api.no_direct_database_access rule.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService


router = APIRouter(prefix="/knowledge")


@router.get("/capabilities")
# ID: 0016df93-d0e5-45b0-b5b8-8f4170de3d9d
async def list_capabilities(
    session: AsyncSession = Depends(service_registry.session),
) -> dict:
    """
    Return known capabilities.

    CONSTITUTIONAL: API routes through Body layer (service_registry) rather than
    directly importing session_manager, maintaining Mind-Body-Will separation.

    Tests expect a 200 on GET /v1/knowledge/capabilities and a JSON object
    with a 'capabilities' key.
    """
    service = KnowledgeService(session=session)
    caps = await service.list_capabilities()
    return {"capabilities": caps}
