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


# ID: 69085115-da2d-4649-948c-690b61eb1751
def register_exception_handlers(app):
    """Registers custom exception handlers with the FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    # ID: 12d85f80-7154-4bbc-a209-5bcf64b1455f
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Handles FastAPI's built-in HTTP exceptions to ensure consistent
        JSON error responses.
        """
        logger.warning(
            "HTTP Exception: %s %s for request: %s %s",
            exc.status_code,
            exc.detail,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "request_error", "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    # ID: cd3d5242-3238-4f47-9224-6b7fd4365503
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Catches any unhandled exception, logs the full traceback internally,
        and returns a generic 500 Internal Server Error to the client.
        This is a critical security measure to prevent leaking stack traces.
        """
        logger.exception(
            "Unhandled exception for request: %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected internal error occurred.",
            },
        )

    logger.info("Registered global exception handlers.")
