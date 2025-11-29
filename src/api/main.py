# src/api/main.py

"""Provides functionality for the main module."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mind.governance.audit_context import AuditorContext
from services.clients.qdrant_client import QdrantService

# FIX: Import Class and Session Manager
from services.config_service import ConfigService
from services.database.session_manager import get_session
from services.git_service import GitService
from services.knowledge.knowledge_service import KnowledgeService
from services.storage.file_handler import FileHandler
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger, reconfigure_log_level
from shared.models import PlannerConfig
from will.orchestration.cognitive_service import CognitiveService

from api.v1 import development_routes, knowledge_routes
from src.shared.errors import register_exception_handlers

logger = getLogger(__name__)


@asynccontextmanager
# ID: 3625601a-e4f9-44c6-a6bc-c6bc194d4d29
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting CORE system...")
    core_context = CoreContext(
        git_service=GitService(settings.REPO_PATH),
        cognitive_service=CognitiveService(settings.REPO_PATH),
        knowledge_service=KnowledgeService(settings.REPO_PATH),
        qdrant_service=QdrantService(),
        auditor_context=AuditorContext(settings.REPO_PATH),
        file_handler=FileHandler(str(settings.REPO_PATH)),
        planner_config=PlannerConfig(),
    )
    app.state.core_context = core_context
    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True
    try:
        if not getattr(core_context, "_is_test_mode", False):
            # FIX: Instantiate ConfigService properly
            async with get_session() as session:
                config = await ConfigService.create(session)
                await config.reload()
                await core_context.cognitive_service.initialize()
                await core_context.auditor_context.load_knowledge_graph()
                log_level_from_db = await config.get("LOG_LEVEL", "INFO")
                reconfigure_log_level(log_level_from_db)
        yield
    finally:
        logger.info("🛑 CORE system shutting down.")


# ID: d05a8460-e1bf-4fd6-8d81-38d9fc98dc5c
def create_app() -> FastAPI:
    app = FastAPI(
        title="CORE - Self-Improving System Architect",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(knowledge_routes.router, prefix="/v1", tags=["Knowledge"])
    app.include_router(development_routes.router, prefix="/v1", tags=["Development"])
    register_exception_handlers(app)

    @app.get("/health")
    # ID: cb7c5393-8cc9-40f6-8563-61ed91b6d5d2
    def health_check():
        return {"status": "ok"}

    return app
