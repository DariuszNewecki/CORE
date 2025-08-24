# src/core/errors.py
"""
Centralizes HTTP exception handling to prevent sensitive stack trace leaks and ensure consistent error responses.
"""

from __future__ import annotations

# src/core/errors.py
"""
Centralized HTTP exception handlers for the CORE FastAPI application.
This module ensures that no unhandled exceptions leak sensitive stack trace
information to the client, aligning with the 'safe_by_default' principle.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.logger import getLogger

log = getLogger("core_api.errors")


def register_exception_handlers(app):
    """Registers custom exception handlers with the FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Handles FastAPI's built-in HTTP exceptions to ensure consistent
        JSON error responses.
        """
        log.warning(
            f"HTTP Exception: {exc.status_code} {exc.detail} for request: {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "request_error", "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Catches any unhandled exception, logs the full traceback internally,
        and returns a generic 500 Internal Server Error to the client.
        This is a critical security measure to prevent leaking stack traces.
        """
        log.exception(
            f"Unhandled exception for request: {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected internal error occurred.",
            },
        )

    log.info("Registered global exception handlers.")
