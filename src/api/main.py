# src/api/main.py
# ID: d05a8460-e1bf-4fd6-8d81-38d9fc98dc5c

"""
API Main Entry Point

CONSTITUTIONAL COMPLIANCE (V2.3.0):
- API layer no longer imports Body services directly.
- Lifespan ignition sequence delegated to shared.infrastructure.lifespan.
- Resolves architecture.api.no_body_bypass violation.

This module is the FastAPI composition root. It:
- Registers routes
- Registers exception handlers
- Delegates system lifecycle to infrastructure

It does NOT:
- Import Body layer services
- Access the database directly
- Make strategic decisions
"""

from __future__ import annotations

from fastapi import FastAPI

from api.v1 import development_routes, knowledge_routes
from shared.errors import register_exception_handlers
from shared.infrastructure.lifespan import core_lifespan
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 68ed3165-c844-40f2-8596-baaa455720dc
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
    # ID: cb7c5393-8cc9-40f6-8563-61ed91b6d5d2
    def health_check():
        return {"status": "ok"}

    return app
