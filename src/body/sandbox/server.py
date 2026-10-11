# src/body/sandbox/server.py
"""
The sandbox service: one connection, one job (ADR-132 D10.10).

Started by systemd per connection (``core-sandbox.socket`` with
``Accept=yes``; the instance gets the connection on standard input) as the
``core-sandbox`` account, inside the walls the unit sets: no network, host
sockets and secrets hidden, the inbox read-only, writes only to ``/work``.
The unit is the isolation; this code only refuses and runs.

Per connection:
1. The kernel's peer credentials must name the one allowed client account
   (``CORE_SANDBOX_CLIENT_USER``, default ``core``); anything else is refused.
2. The job is read (size-capped) and validated.
3. Its snapshot must be a directory directly under the inbox root
   (``CORE_SANDBOX_INBOX_ROOT``), named by the job id, reached without
   following links.
4. The job runs (``runner.run_job``) in the instance's scratch directory
   ``CORE_SANDBOX_WORK_ROOT``; the result goes back on the connection.

Entry point: ``python -I -m body.sandbox.server``.

CONSTITUTIONAL ALIGNMENT:
- Runs only as the sandbox account, from the release. Holds no credential.
"""

from __future__ import annotations

import os
import pwd
import socket
import stat
import struct
import sys
from pathlib import Path
from typing import Any

from body.sandbox.models import JobRejected, SandboxJob, SandboxResult
from body.sandbox.protocol import (
    MAX_JOB_BYTES,
    ProtocolError,
    encode,
    recv_message,
)
from body.sandbox.runner import run_job
from shared.logger import getLogger


logger = getLogger(__name__)

ISOLATION = "service"
_STDIN_FD = 0
_UCRED = struct.Struct("3i")  # struct ucred, as api/serve.read_peer_cred reads it


# ID: c9051fbc-58e5-4b3e-9c4d-a267e27d3f8b
def allowed_client_uid(environ: dict[str, str]) -> int:
    """The uid of the one account allowed to submit jobs."""
    return pwd.getpwnam(environ.get("CORE_SANDBOX_CLIENT_USER", "core")).pw_uid


# ID: d26e90a6-266d-4e91-8057-b39b238cd6a8
def peer_uid(sock: socket.socket) -> int:
    """The connecting process's uid, as the kernel reports it (SO_PEERCRED)."""
    if sock.family != socket.AF_UNIX:
        raise PermissionError("not a Unix socket: no peer credentials")
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, _UCRED.size)
    _pid, uid, _gid = _UCRED.unpack(raw)
    return int(uid)


# ID: caae0c40-25c9-4741-bf91-1d27e698c518
def open_snapshot(inbox_root: Path, job_id: str) -> Path:
    """The job's snapshot directory, refused unless it is a real directory
    directly under the inbox root (no links followed)."""
    root_fd = os.open(inbox_root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        fd = os.open(
            job_id,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
    except OSError as exc:
        raise JobRejected(f"snapshot {job_id} is not a directory: {exc}") from exc
    finally:
        os.close(root_fd)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise JobRejected(f"snapshot {job_id} is not a directory")
    finally:
        os.close(fd)
    return inbox_root / job_id


# ID: 1ccdc6c6-0343-4233-a197-4f69f9235573
def handle_connection(sock: socket.socket, environ: dict[str, str]) -> dict[str, Any]:
    """Serve one job on *sock*; return the result that was (or would be) sent."""
    if peer_uid(sock) != allowed_client_uid(environ):
        result = SandboxResult.not_run(
            ISOLATION, "refused: caller is not the client account"
        )
        _send(sock, result.to_dict())
        return result.to_dict()
    try:
        job = SandboxJob.from_dict(recv_message(sock, MAX_JOB_BYTES).get("job", {}))
        snapshot = open_snapshot(Path(environ["CORE_SANDBOX_INBOX_ROOT"]), job.job_id)
        # One job per unit instance: the instance's own scratch (a tmpfs the
        # unit mounts, discarded when the instance ends) is the work dir.
        work_dir = Path(environ.get("CORE_SANDBOX_WORK_ROOT", "/work"))
        result = run_job(
            job, snapshot_dir=snapshot, work_dir=work_dir, isolation=ISOLATION
        )
    except (JobRejected, ProtocolError, KeyError, OSError) as exc:
        result = SandboxResult.not_run(ISOLATION, f"refused: {exc}")
    _send(sock, result.to_dict())
    return result.to_dict()


def _send(sock: socket.socket, message: dict[str, Any]) -> None:
    try:
        sock.sendall(encode({"result": message}))
    except OSError as exc:
        logger.warning("sandbox: result could not be sent: %s", exc)


# ID: a78b1bad-a3c9-412b-969f-5508e5f87ecb
def main() -> int:
    sock = socket.socket(fileno=os.dup(_STDIN_FD))
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, _STDIN_FD)  # the connection stays with this process only
    os.close(devnull)
    try:
        handle_connection(sock, dict(os.environ))
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
