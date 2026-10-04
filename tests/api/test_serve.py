# tests/api/test_serve.py
"""core-api launcher: kernel peer credentials reach the handler (ADR-132 D10.1)."""

from __future__ import annotations

import asyncio
import os
import socket
import stat
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request

from api.serve import (
    PEER_CRED_EXTENSION,
    bind_tcp_socket,
    bind_unix_socket,
    build_config,
    read_peer_cred,
)


@pytest.fixture
def short_dir(tmp_path: Path) -> Path:
    """tmp_path, if short enough for an AF_UNIX path (108-byte limit)."""
    if len(str(tmp_path)) > 90:
        pytest.skip(f"tmp_path too long for a Unix socket: {tmp_path}")
    return tmp_path


def _whoami_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(request: Request) -> dict[str, Any]:
        return {
            "peer": (request.scope.get("extensions") or {}).get(PEER_CRED_EXTENSION)
        }

    return app


async def _serve_and_get(sock: socket.socket, client: httpx.AsyncClient) -> Any:
    server = uvicorn.Server(build_config(_whoami_app(), log_level="warning"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        # The socket is already listening, so the request waits in the
        # kernel backlog until the server starts accepting.
        return (await client.get("/whoami")).json()
    finally:
        server.should_exit = True
        await task


async def test_unix_socket_caller_uid_reaches_handler(short_dir: Path) -> None:
    path = short_dir / "api.sock"
    sock = bind_unix_socket(path)
    transport = httpx.AsyncHTTPTransport(uds=str(path))
    async with httpx.AsyncClient(transport=transport, base_url="http://core") as client:
        body = await _serve_and_get(sock, client)
    assert body["peer"]["uid"] == os.getuid()
    assert body["peer"]["pid"] == os.getpid()


async def test_tcp_caller_has_no_identity() -> None:
    sock = bind_tcp_socket("127.0.0.1", 0)
    port = sock.getsockname()[1]
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        body = await _serve_and_get(sock, client)
    assert body["peer"] is None


def test_unix_socket_mode_is_0660(short_dir: Path) -> None:
    path = short_dir / "m.sock"
    sock = bind_unix_socket(path)
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o660
    finally:
        sock.close()


def test_existing_socket_is_refused_not_removed(short_dir: Path) -> None:
    path = short_dir / "s.sock"
    bind_unix_socket(path).close()
    with pytest.raises(FileExistsError):
        bind_unix_socket(path)
    assert stat.S_ISSOCK(path.lstat().st_mode)


def test_non_socket_file_is_refused(short_dir: Path) -> None:
    path = short_dir / "f.sock"
    path.write_text("not a socket", encoding="utf-8")
    with pytest.raises(FileExistsError):
        bind_unix_socket(path)
    assert path.read_text(encoding="utf-8") == "not a socket"


def test_read_peer_cred_ignores_non_unix_sockets() -> None:
    assert read_peer_cred(None) is None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
        assert read_peer_cred(tcp) is None
