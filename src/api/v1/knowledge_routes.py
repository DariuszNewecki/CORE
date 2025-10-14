# src/api/v1/knowledge_routes.py
from __future__ import annotations

from fastapi import APIRouter

from core.knowledge_service import KnowledgeService

# Prefix aligns with test path: /v1/knowledge/capabilities
router = APIRouter(prefix="/knowledge")


@router.get("/capabilities")
# ID: 0016df93-d0e5-45b0-b5b8-8f4170de3d9d
async def list_capabilities() -> dict:
    """
    Return known capabilities.

    Tests expect a 200 on GET /v1/knowledge/capabilities and a JSON object
    with a 'capabilities' key.
    """
    service = KnowledgeService()
    caps = await service.list_capabilities()
    return {"capabilities": caps}
