# tests/api/cli/test_client_unix_socket.py
"""CoreApiClient reaches CORE over its Unix socket (ADR-132 D10.6 step 2)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI, Request

from api.cli.client import CoreApiClient, parse_base_url
from api.serve import PEER_CRED_EXTENSION, bind_unix_socket, build_config


def test_http_url_is_unchanged() -> None:
    assert parse_base_url("http://127.0.0.1:8000") == ("http://127.0.0.1:8000", None)


def test_unix_url_names_the_socket() -> None:
    assert parse_base_url("unix:///run/core/api/api.sock") == (
        "http://localhost",
        "/run/core/api/api.sock",
    )


def test_relative_unix_path_is_refused() -> None:
    with pytest.raises(ValueError, match="absolute"):
        parse_base_url("unix://run/core/api/api.sock")


async def test_requests_go_over_the_socket_with_the_callers_uid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if len(str(tmp_path)) > 90:
        pytest.skip(f"tmp_path too long for a Unix socket: {tmp_path}")
    app = FastAPI()

    @app.post("/v1/echo")
    async def echo(request: Request) -> dict[str, Any]:
        return {"peer": (request.scope.get("extensions") or {})[PEER_CRED_EXTENSION]}

    path = tmp_path / "api.sock"
    sock = bind_unix_socket(path)
    server = uvicorn.Server(build_config(app, log_level="warning"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    monkeypatch.setenv("CORE_API_URL", f"unix://{path}")
    try:
        body = await CoreApiClient()._request("POST", "/v1/echo")
    finally:
        server.should_exit = True
        await task
    assert body["peer"]["uid"] == os.getuid()
