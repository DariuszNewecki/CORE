# src/shared/errors.py

"""
Centralizes HTTP exception handling to prevent sensitive stack trace leaks and ensure consistent error responses.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.logger import getLogger

logger = getLogger(__name__)


# ID: e10a3e1f-de3d-49d7-a378-fc00b89ab3fa
def register_exception_handlers(app):
    """Registers custom exception handlers with the FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    # ID: 49273af2-dd45-4e08-9695-d372ff56948c
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Handles FastAPI's built-in HTTP exceptions to ensure consistent
        JSON error responses.
        """
        logger.warning(
            f"HTTP Exception: {exc.status_code} {exc.detail} for request: {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "request_error", "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    # ID: bcb88b79-942f-4057-8998-d977165e156d
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Catches any unhandled exception, logs the full traceback internally,
        and returns a generic 500 Internal Server Error to the client.
        This is a critical security measure to prevent leaking stack traces.
        """
        logger.exception(
            f"Unhandled exception for request: {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected internal error occurred.",
            },
        )

    logger.info("Registered global exception handlers.")
