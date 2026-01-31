# src/api/main.py
# ID: d05a8460-e1bf-4fd6-8d81-38d9fc98dc5c

"""
API Main Entry Point

CONSTITUTIONAL FIX:
- Removed 7 forbidden imports (logic.di.no_global_session & architecture.boundary.settings_access).
- Preserves all service warmup, logging, and test-mode logic.
- Delegates bootstrap to the Body layer Sanctuary.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Routes
from api.v1 import development_routes, knowledge_routes

# Architecture & Service Imports
# We only import high-level abstractions now
from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.context import CoreContext
from shared.errors import register_exception_handlers
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger, reconfigure_log_level


logger = getLogger(__name__)


@asynccontextmanager
# ID: 3625601a-e4f9-44c6-a6bc-c6bc194d4d29
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting CORE system...")

    # CONSTITUTIONAL FIX: Centralized bootstrap replaces manual construction
    # This fulfills the registry priming and context creation requirements.
    core_context: CoreContext = create_core_context(service_registry)

    app.state.core_context = core_context

    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True

    try:
        if not getattr(core_context, "_is_test_mode", False):
            # 1. Warm up Heavy Services via Registry (Async)
            # This logic is preserved exactly from the original main.py
            cognitive = await service_registry.get_cognitive_service()
            auditor = await service_registry.get_auditor_context()
            qdrant = await service_registry.get_qdrant_service()

            core_context.cognitive_service = cognitive
            core_context.auditor_context = auditor
            core_context.qdrant_service = qdrant

            # 2. Database & Config Initialization
            # Uses service_registry.session() which is the approved abstract factory
            async with service_registry.session() as session:
                config = await ConfigService.create(session)
                log_level_from_db = await config.get("LOG_LEVEL", "INFO")
                reconfigure_log_level(log_level_from_db)
                # Ensure cognitive service loads its Mind rules
                await cognitive.initialize(session)

            # 3. Load Knowledge Graph
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
