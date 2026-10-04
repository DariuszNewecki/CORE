# src/api/serve.py
"""
core-api launcher: one process, two listeners, kernel-supplied caller identity.

ADR-132 D10.1: a local caller's identity comes from the kernel, as the peer
credentials (``SO_PEERCRED``) of a Unix-domain socket connection. Never from
a request body or header, a flag or an environment variable.

``PeerCredH11Protocol`` reads them when a connection opens and puts them in
every request's ASGI scope as ``scope["extensions"]["peer_cred"]``
(``{"pid", "uid", "gid"}``). On a TCP connection the value is ``None``: TCP
carries no identity and can never be a governor (ADR-132 D10.3 as amended).

The uvicorn CLI accepts only its built-in protocol names, and
``uvicorn[standard]`` would pick httptools by default, so the protocol is
pinned here and the API is launched with::

    python -m api.serve --uds <socket path> [--host 127.0.0.1] [--port 8000]

The socket's directory and group are deployment concerns (D10.3 as amended:
a ``core``-owned directory whose group excludes the assistant). This module
only sets the socket's own mode to 0660.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import struct
from pathlib import Path
from typing import Any

import uvicorn
from uvicorn.protocols.http.h11_impl import H11Protocol

from shared.logger import getLogger


logger = getLogger(__name__)

PEER_CRED_EXTENSION = "peer_cred"
_UCRED = struct.Struct("3i")


# ID: 08333d8f-8ab6-48a7-850a-83ccb96988d7
def read_peer_cred(sock: socket.socket | None) -> dict[str, int] | None:
    """Kernel peer credentials of a Unix-socket connection, else None."""
    if sock is None or sock.family != socket.AF_UNIX:
        return None
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, _UCRED.size)
    pid, uid, gid = _UCRED.unpack(raw)
    return {"pid": pid, "uid": uid, "gid": gid}


class _WithPeerCred:
    """ASGI wrapper stamping one connection's peer credentials into its scopes."""

    def __init__(self, app: Any, peer_cred: dict[str, int] | None) -> None:
        self._app = app
        self._peer_cred = peer_cred

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        extensions = dict(scope.get("extensions") or {})
        extensions[PEER_CRED_EXTENSION] = self._peer_cred
        scope["extensions"] = extensions
        await self._app(scope, receive, send)


# ID: 7eaca622-bf3e-4c7a-ad40-00dec6d4a484
class PeerCredH11Protocol(H11Protocol):
    """h11 protocol that exposes the connection's kernel peer credentials."""

    # ID: 964d2ddf-9787-443b-bca2-efb6bff9e1fe
    def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
        peer_cred = read_peer_cred(transport.get_extra_info("socket"))
        self.app = _WithPeerCred(self.app, peer_cred)
        super().connection_made(transport)


# ID: 8729f9ae-c5ec-462b-b4e1-b419a5f6e645
def bind_unix_socket(path: Path) -> socket.socket:
    """Bind a listening Unix socket at *path* with mode 0660.

    Anything already at *path* is refused, never removed: the deployment
    provides a fresh directory per run (systemd ``RuntimeDirectory=``), so a
    leftover file means something else is using the path. The mode comes
    from the umask at bind time; the launcher is single-threaded here.
    """
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"{path} already exists")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    previous_umask = os.umask(0o117)
    try:
        sock.bind(str(path))
    finally:
        os.umask(previous_umask)
    sock.listen(socket.SOMAXCONN)
    return sock


# ID: c01d3424-c64a-48ca-bf07-1a4fc2263ecb
def bind_tcp_socket(host: str, port: int) -> socket.socket:
    """Bind a listening TCP socket on *host*:*port*."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(socket.SOMAXCONN)
    return sock


# ID: e5fb60e3-e2f8-4433-a14f-bb7afa6a1b16
def build_config(app: Any = "api.main:app", log_level: str = "info") -> uvicorn.Config:
    """uvicorn config with the peer-credential protocol pinned."""
    return uvicorn.Config(app, http=PeerCredH11Protocol, log_level=log_level)


# ID: d1afafa9-7a13-4904-8263-2978ded03074
def main(argv: list[str] | None = None) -> None:
    """Serve the API on TCP (user-facing) and a Unix socket (identity-bearing)."""
    parser = argparse.ArgumentParser(prog="python -m api.serve")
    parser.add_argument("--uds", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(argv)

    sockets = [bind_tcp_socket(args.host, args.port), bind_unix_socket(args.uds)]
    logger.info("core-api listening on %s:%d and %s", args.host, args.port, args.uds)
    uvicorn.Server(build_config(log_level=args.log_level)).run(sockets=sockets)


if __name__ == "__main__":
    main()
