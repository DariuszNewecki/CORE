# src/body/sandbox/protocol.py
"""
Wire format between CORE and the sandbox service (ADR-132 D10.10).

One connection carries one job and one result. Each message is a 4-byte
big-endian length followed by that many bytes of UTF-8 JSON. Lengths are
capped on read, so a peer cannot make the other side buffer without bound.

CONSTITUTIONAL ALIGNMENT:
- Pure framing. Socket I/O only; no filesystem access.
"""

from __future__ import annotations

import asyncio
import json
import socket
import struct
from typing import Any


MAX_JOB_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 8 * 1024 * 1024
_HEADER = struct.Struct(">I")


# ID: 40d477dc-88b8-4131-b20a-4a6b97ef2b06
class ProtocolError(ValueError):
    """A message was malformed, oversized or cut short."""


# ID: 5a26b682-2c56-4a88-8dda-c9b2ce38aa6b
def encode(message: dict[str, Any]) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return _HEADER.pack(len(body)) + body


# ID: 2093aea4-1fe7-4dde-8c52-f316721cfd75
def decode_body(body: bytes) -> dict[str, Any]:
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError(f"not JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message is not an object")
    return message


# ID: bd8d268b-3f6f-4741-93e4-4a26b0eada60
def recv_message(sock: socket.socket, max_bytes: int) -> dict[str, Any]:
    """Blocking read of one framed message (the service side)."""
    (length,) = _HEADER.unpack(_recv_exact(sock, _HEADER.size))
    if length > max_bytes:
        raise ProtocolError(f"message of {length} bytes exceeds {max_bytes}")
    return decode_body(_recv_exact(sock, length))


# ID: 54ac374a-0e56-4496-823a-7cb145688ae9
async def read_message(reader: asyncio.StreamReader, max_bytes: int) -> dict[str, Any]:
    """Async read of one framed message (the client side)."""
    try:
        (length,) = _HEADER.unpack(await reader.readexactly(_HEADER.size))
        if length > max_bytes:
            raise ProtocolError(f"message of {length} bytes exceeds {max_bytes}")
        return decode_body(await reader.readexactly(length))
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError("connection closed mid-message") from exc


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(min(remaining, 65536))
        if not chunk:
            raise ProtocolError("connection closed mid-message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
