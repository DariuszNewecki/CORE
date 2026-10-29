from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from api.errors import register_exception_handlers


# ID: 079a59d8-9393-43c4-b4dd-a9b416c53d19
def test_register_exception_handlers():
    app = FastAPI()

    with patch("api.errors.logger") as mock_logger:
        register_exception_handlers(app)

    # Both handlers should be registered.
    handlers = app.exception_handlers
    assert StarletteHTTPException in handlers
    assert Exception in handlers

    http_handler = handlers[StarletteHTTPException]
    unhandled_handler = handlers[Exception]

    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"

    # Happy path: HTTP exception handler returns JSON response.
    http_exc = StarletteHTTPException(status_code=404, detail="Not found")
    http_response = asyncio.run(http_handler(request, http_exc))
    assert http_response.status_code == 404

    # Happy path: unhandled exception handler returns generic 500.
    unhandled_response = asyncio.run(unhandled_handler(request, RuntimeError("boom")))
    assert unhandled_response.status_code == 500
