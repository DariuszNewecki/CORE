# src/api/v1/knowledge_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.knowledge_service import KnowledgeService

router = APIRouter()


# ID: 862c26cd-621c-4cd4-990c-119af2755e79
def get_knowledge_service() -> KnowledgeService:
    # Lightweight provider; the test patches KnowledgeService.list_capabilities on this path
    return KnowledgeService()


@router.get("/capabilities")
# ID: 115783e4-7605-49e0-be12-e389a4cb5883
async def list_capabilities(
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    caps = await service.list_capabilities()
    # The test asserts: {"capabilities": ["test.cap"]}
    return {"capabilities": caps}
