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
    """
        Creates and configures a FastAPI application with routers, exception handlers, and a health check.
    Args: None.
    Returns: Configured FastAPI instance.
    """
    """
    This function initializes a FastAPI instance, adds three routers for handling different types of requests, configures exception handlers for various errors, includes a health check endpoint to monitor application status, and returns the configured FastAPI application.
    """
    """
    This function initializes a FastAPI instance, adds three routers to handle different types of requests, configures exception handling for various error scenarios, includes a health check endpoint to monitor the application's status, and returns the configured FastAPI application.
    """
    """
        This function creates a FastAPI instance with three routers, registers exception handlers, includes health check endpoint, and returns the configured application instance.

    plaintext
    Args:
        None

    Returns:
        FastAPI object
    """
    """
    Summarize the code for create_app function to create a FastAPI instance with three routers, exception handlers, health check endpoint, and return it.
    """
    """
        This function creates a FastAPI application with three routers, registers exception handlers, includes health check endpoint, and returns the configured application instance.

    Args:
    - None

    Returns:
    - FastAPI object
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
