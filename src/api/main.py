# src/api/main.py

"""
API Main Entry Point — composition root.

FastAPI requires `lifespan` to be declared at app creation, so this file
imports `core_lifespan` from Body to wire the startup/shutdown sequence.
Composition roots wire layers together by design and are not layer bypasses.

CONSTITUTIONAL STATUS:
- Exempted from `architecture.api.no_body_bypass` via the composition-root
  sanctuary in `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  (added 2026-04-19). Analogous to the bootstrap sanctuary granted under
  `architecture.shared.no_layer_imports` for shared-layer composition files.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.errors import register_exception_handlers
from api.v1 import development_routes, knowledge_routes
from body.infrastructure.lifespan import core_lifespan
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2751f337-a513-4f6d-8f35-b9d7055faac0
def create_app() -> FastAPI:
    """
    This function creates a FastAPI application with two routers, registers exception handlers, includes health check endpoint, and returns the configured application instance.
    """
    app = FastAPI(
        title="CORE - Self-Improving System Architect",
        version="1.0.0",
        lifespan=core_lifespan,
    )
    app.include_router(knowledge_routes.router, prefix="/v1", tags=["Knowledge"])
    app.include_router(development_routes.router, prefix="/v1", tags=["Development"])
    register_exception_handlers(app)

    @app.get("/health")
    # ID: 7e958d32-1b47-43a5-836b-f6df51d6b803
    def health_check():
        return {"status": "ok"}

    return app
