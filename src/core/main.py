# src/core/main.py
"""
The main entry point for the CORE FastAPI application.
Initializes the application, sets up lifespan events, and includes all API routers.
"""

from __future__ import annotations

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

log = getLogger("core.main")


@asynccontextmanager
# ID: 3a81d3db-83ee-4c34-ba20-c8cad6bda79c
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    log.info("🚀 Starting CORE system...")

    # Create and attach the shared CoreContext to the application state
    core_context = CoreContext(
        git_service=GitService(settings.REPO_PATH),
        cognitive_service=CognitiveService(settings.REPO_PATH),
        qdrant_service=QdrantService(),
        auditor_context=AuditorContext(settings.REPO_PATH),
        file_handler=FileHandler(str(settings.REPO_PATH)),
        planner_config=PlannerConfig(),
    )
    app.state.core_context = core_context

    try:
        # Initialize services that need async setup
        await core_context.cognitive_service.initialize()
        await core_context.auditor_context.load_knowledge_graph()
        yield
    finally:
        log.info("🛑 CORE system shutting down.")


# ID: 4fe42369-b346-44e8-8cb4-e6e298dffcb8
def create_app() -> FastAPI:
    """Creates and configures the main FastAPI application instance."""
    app = FastAPI(
        title="CORE - Self-Improving System Architect",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Register routers
    app.include_router(knowledge_routes.router, prefix="/v1", tags=["Knowledge"])
    app.include_router(development_routes.router, prefix="/v1", tags=["Development"])

    # Register exception handlers for robust error responses
    register_exception_handlers(app)

    @app.get("/health")
    # ID: 3ade1e85-161c-4b2c-bf1b-721774082d61
    def health_check():
        return {"status": "ok"}

    return app
