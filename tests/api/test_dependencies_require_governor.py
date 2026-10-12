# tests/api/test_dependencies_require_governor.py
"""require_governor is live: only the bound governor on the Unix socket passes.

ADR-132 D10.3 as amended and D10.9. Served for real through api.serve's
peer-credential protocol, so the identity comes from the kernel, as in
deployment; only the principal binding is substituted.
"""

from __future__ import annotations

import asyncio
import os
import pwd
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

import api.dependencies as deps
from api.serve import bind_tcp_socket, bind_unix_socket, build_config
from shared.infrastructure.principal_binding import GOVERNOR, PrincipalBinding


ME = os.getuid()


@pytest.fixture
def short_dir(tmp_path: Path) -> Path:
    """tmp_path, if short enough for an AF_UNIX path (108-byte limit)."""
    if len(str(tmp_path)) > 90:
        pytest.skip(f"tmp_path too long for a Unix socket: {tmp_path}")
    return tmp_path


def _bind(monkeypatch: pytest.MonkeyPatch, binding: PrincipalBinding) -> None:
    monkeypatch.setattr(deps, "load_principal_binding", lambda: binding)


def _gated_app() -> FastAPI:
    app = FastAPI()

    @app.post("/act")
    async def act(user: dict = deps.require_governor) -> dict[str, Any]:
        return user

    return app


async def _post(sock: socket.socket, client: httpx.AsyncClient) -> httpx.Response:
    server = uvicorn.Server(build_config(_gated_app(), log_level="warning"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        return await client.post("/act")
    finally:
        server.should_exit = True
        await task


async def _post_unix(path: Path) -> httpx.Response:
    sock = bind_unix_socket(path)
    transport = httpx.AsyncHTTPTransport(uds=str(path))
    async with httpx.AsyncClient(transport=transport, base_url="http://core") as client:
        return await _post(sock, client)


async def test_bound_governor_on_the_socket_passes_and_is_named(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, PrincipalBinding(roles_by_uid={ME: GOVERNOR}))
    response = await _post_unix(short_dir / "api.sock")
    assert response.status_code == 200
    assert response.json() == {
        "sub": pwd.getpwuid(ME).pw_name,
        "principal": GOVERNOR,
    }


async def test_unbound_account_on_the_socket_is_refused(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, PrincipalBinding(roles_by_uid={ME + 1: GOVERNOR}))
    response = await _post_unix(short_dir / "api.sock")
    assert response.status_code == 403
    assert "not bound" in response.json()["detail"]


async def test_another_role_on_the_socket_is_refused(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(monkeypatch, PrincipalBinding(roles_by_uid={ME: "principal.operator"}))
    response = await _post_unix(short_dir / "api.sock")
    assert response.status_code == 403


async def test_missing_binding_means_nobody_is_governor(
    short_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind(
        monkeypatch, PrincipalBinding(error="/etc/core/principals.yaml does not exist")
    )
    response = await _post_unix(short_dir / "api.sock")
    assert response.status_code == 403
    assert "does not exist" in response.json()["detail"]


async def test_tcp_is_refused_even_for_the_bound_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(monkeypatch, PrincipalBinding(roles_by_uid={ME: GOVERNOR}))
    sock = bind_tcp_socket("127.0.0.1", 0)
    port = sock.getsockname()[1]
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        response = await _post(sock, client)
    assert response.status_code == 403
    assert "Unix socket" in response.json()["detail"]


def test_the_oss_passthrough_is_gone() -> None:
    assert not hasattr(deps, "_oss_passthrough")
    assert not hasattr(deps, "require_operator")
