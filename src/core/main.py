# src/core/main.py
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from api.v1 import development_routes, knowledge_routes
from fastapi import FastAPI
from features.governance.audit_context import AuditorContext
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlannerConfig

from core.cognitive_service import CognitiveService
from core.errors import register_exception_handlers
from core.file_handler import FileHandler
from core.git_service import GitService
from core.knowledge_service import KnowledgeService

log = getLogger("core.main")


@asynccontextmanager
# ID: 955908bb-6979-42b9-95fb-67f61a75db12
async def lifespan(app: FastAPI):
    log.info("🚀 Starting CORE system...")
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

    # If running under pytest, let tests control initialization order explicitly
    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True  # tests call init/load explicitly

    try:
        if not getattr(core_context, "_is_test_mode", False):
            await core_context.cognitive_service.initialize()
            await core_context.auditor_context.load_knowledge_graph()
        yield
    finally:
        log.info("🛑 CORE system shutting down.")


# ID: ac2f33e7-4aed-4d32-b701-9bc50b622016
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
    # ID: ee809a0b-21da-4169-a197-cf5df1d9ada8
    def health_check():
        return {"status": "ok"}

    return app
