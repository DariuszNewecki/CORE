# src/api/main.py

"""Provides functionality for the main module."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Routes
from api.v1 import development_routes, knowledge_routes

# Architecture & Service Imports
from body.services.service_registry import service_registry
from shared.config import settings
from shared.context import CoreContext
from shared.errors import register_exception_handlers
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger, reconfigure_log_level
from shared.models import PlannerConfig


logger = getLogger(__name__)


def _build_context_service() -> ContextService:
    """
    Factory for ContextService, wired for the API context.
    Ensures the API uses the same context logic as the CLI.
    """
    return ContextService(
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
        # Qdrant/Cognitive services are loaded lazily by ContextService if not passed
    )


@asynccontextmanager
# ID: 3625601a-e4f9-44c6-a6bc-c6bc194d4d29
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting CORE system...")

    # 1. Initialize CoreContext with the Singleton Registry
    # This prevents "Split-Brain" by using the same service container as the CLI.
    core_context = CoreContext(
        registry=service_registry,
        # Initialize lightweight components that don't manage connection pools
        git_service=GitService(settings.REPO_PATH),
        file_handler=FileHandler(str(settings.REPO_PATH)),
        planner_config=PlannerConfig(),
        knowledge_service=KnowledgeService(settings.REPO_PATH),
    )

    # Wire the factory for ContextService (Required for Autonomous Developer)
    core_context.context_service_factory = _build_context_service

    app.state.core_context = core_context

    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True

    try:
        if not getattr(core_context, "_is_test_mode", False):
            # 2. Warm up Heavy Services via Registry (Async)
            # This ensures we use the singleton instances managed by ServiceRegistry
            # instead of creating new ones with separate connection pools.
            cognitive = await service_registry.get_cognitive_service()
            auditor = await service_registry.get_auditor_context()
            qdrant = await service_registry.get_qdrant_service()

            # Backfill legacy context fields for routes that rely on them directly
            core_context.cognitive_service = cognitive
            core_context.auditor_context = auditor
            core_context.qdrant_service = qdrant

            # 3. Database & Config Initialization
            async with get_session() as session:
                config = await ConfigService.create(session)

                # Apply logging configuration from DB
                log_level_from_db = await config.get("LOG_LEVEL", "INFO")
                reconfigure_log_level(log_level_from_db)

                # Initialize Agents/Roles from DB (Mind Layer)
                await cognitive.initialize()

            # 4. Load Knowledge Graph (for Auditor/Safety Checks)
            await auditor.load_knowledge_graph()

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
