# src/api/v1/knowledge_routes.py

"""Provides functionality for the knowledge_routes module."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from services.database.session_manager import get_db_session
from services.knowledge.knowledge_service import KnowledgeService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/knowledge")


@router.get("/capabilities")
# ID: 0016df93-d0e5-45b0-b5b8-8f4170de3d9d
async def list_capabilities(session: AsyncSession = Depends(get_db_session)) -> dict:
    """
    Return known capabilities.

    Tests expect a 200 on GET /v1/knowledge/capabilities and a JSON object
    with a 'capabilities' key.
    """
    service = KnowledgeService(session=session)
    caps = await service.list_capabilities()
    return {"capabilities": caps}
