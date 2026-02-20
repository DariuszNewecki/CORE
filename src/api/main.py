# src/api/main.py

"""
API Main Entry Point

CONSTITUTIONAL COMPLIANCE:
- API layer no longer imports Body services directly.
- Lifespan ignition sequence delegated to body.infrastructure.lifespan.
- Resolves architecture.api.no_body_bypass violation.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.v1 import development_routes, knowledge_routes
from body.infrastructure.lifespan import core_lifespan
from shared.errors import register_exception_handlers
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2751f337-a513-4f6d-8f35-b9d7055faac0
def create_app() -> FastAPI:
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
