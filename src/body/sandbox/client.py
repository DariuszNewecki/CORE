# src/body/sandbox/client.py
"""
The one door through which CORE runs repository code (ADR-132 D10.10).

``run_repo_code`` copies an allow-listed snapshot of a tree into the inbox
(``var/tmp/sandbox-inbox/<job-id>/`` under the bound repository, through
FileHandler), then runs the job in one of two modes:

- ``service``: the job goes to the sandbox service over its Unix socket and
  runs as ``core-sandbox``, with no network, no host sockets, no secrets.
  Integration-marked tests are excluded (no database there) and reported.
  If the socket is missing, refuses or times out, the result is ``not_run``:
  there is no fallback to a local run, and it is never a pass.
- ``local`` (open CORE default, CI, machines without the service): the same
  snapshot, bootstrap, environment allow-list and result rules, run as the
  caller. Results say ``isolation: local``; this mode does not close R4.

The snapshot digest is computed here, before the job runs, and bound to the
result. The inbox and scratch directories are removed afterwards.

CONSTITUTIONAL ALIGNMENT:
- Writes only through FileHandler, inside the repository (repository
  containment). Mode and socket path are passed in; no settings import.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

from body.infrastructure.storage.file_handler import FileHandler
from body.sandbox.models import COLLECT_KIND, JobRejected, SandboxJob, SandboxResult
from body.sandbox.protocol import (
    MAX_RESULT_BYTES,
    ProtocolError,
    encode,
    read_message,
)
from body.sandbox.runner import run_job
from body.sandbox.snapshot import (
    DEFAULT_INCLUDE,
    SnapshotRefused,
    apply_overlay,
    read_snapshot,
    snapshot_digest,
)
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

MODES: tuple[str, ...] = ("local", "service")
DEFAULT_SOCKET = Path("/run/core/sandbox.sock")
INBOX_DIRNAME = "sandbox-inbox"
WORK_DIRNAME = "sandbox-work"
# Time the service may need beyond the job's own timeout (start, copy, report).
_SERVICE_SLACK_SEC = 60


@dataclass(frozen=True)
# ID: 2826edee-06eb-4716-b395-95ed937caf9e
class SandboxRequest:
    """What a caller wants run: a tree and the pytest targets inside it."""

    tree: Path
    targets: tuple[str, ...]
    timeout_sec: int
    markers: str | None = None
    include: tuple[str, ...] = DEFAULT_INCLUDE
    # Law roots copied in as .intent/ and .specs/ (see read_snapshot).
    law: tuple[Path, ...] = ()
    # Files added to (or replacing files of) the copy: (relative path, bytes).
    # Code that exists only in memory -- a generated test, a workspace's
    # uncommitted files -- runs without being written into the tree.
    overlay: tuple[tuple[str, bytes], ...] = ()
    # Collect only (pytest --collect-only), run nothing.
    collect_only: bool = False
    # Measure coverage of src/; the result's ``coverage`` carries it.
    coverage: bool = False


# ID: 7017d79f-4d5d-4892-8ff6-5f96a37a8e24
async def run_repo_code(
    request: SandboxRequest,
    *,
    repo_root: Path,
    mode: str,
    socket_path: Path = DEFAULT_SOCKET,
) -> SandboxResult:
    """Run *request* in the sandbox. Never raises for a job that did not run:
    that is a ``not_run`` result."""
    if mode not in MODES:
        return SandboxResult.not_run(mode, f"unknown sandbox mode: {mode!r}")
    job = SandboxJob(
        job_id=uuid.uuid4().hex,
        kind=COLLECT_KIND if request.collect_only else "pytest",
        targets=tuple(request.targets),
        timeout_sec=request.timeout_sec,
        markers=request.markers,
        exclude_integration=(mode == "service"),
        coverage=request.coverage,
    )
    try:
        job.validate()
    except JobRejected as exc:
        return SandboxResult.not_run(mode, f"refused: {exc}")

    handler = FileHandler(str(repo_root))
    tmp_rel = PathResolver(repo_root).tmp_dir.relative_to(handler.repo_path)
    inbox_rel = str(tmp_rel / INBOX_DIRNAME / job.job_id)
    work_rel = str(tmp_rel / WORK_DIRNAME / job.job_id)
    try:
        entries = await asyncio.to_thread(
            read_snapshot, request.tree, request.include, request.law
        )
        entries = apply_overlay(entries, request.overlay)
        digest = snapshot_digest(entries)
        handler.write_snapshot(inbox_rel, entries)
    except (SnapshotRefused, OSError, ValueError) as exc:
        handler.remove_tree(inbox_rel)
        return SandboxResult.not_run(mode, f"snapshot refused: {exc}")

    try:
        if mode == "service":
            result = await _run_in_service(job, socket_path)
        else:
            handler.ensure_dir(work_rel)
            result = await asyncio.to_thread(
                run_job,
                job,
                snapshot_dir=handler.repo_path / inbox_rel,
                work_dir=handler.repo_path / work_rel,
                isolation="local",
            )
    finally:
        handler.remove_tree(inbox_rel)
        if mode == "local":
            handler.remove_tree(work_rel)
    result.snapshot_sha256 = digest
    return result


async def _run_in_service(job: SandboxJob, socket_path: Path) -> SandboxResult:
    """Send *job* to the service; any failure to get a result is ``not_run``."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path)), timeout=10
        )
    except (OSError, TimeoutError) as exc:
        return SandboxResult.not_run("service", f"sandbox service unavailable: {exc}")
    try:
        writer.write(encode({"job": job.to_dict()}))
        await writer.drain()
        message = await asyncio.wait_for(
            read_message(reader, MAX_RESULT_BYTES),
            timeout=job.timeout_sec + _SERVICE_SLACK_SEC,
        )
        result = SandboxResult.from_dict(message["result"])
    except (OSError, TimeoutError, ProtocolError, KeyError, TypeError) as exc:
        return SandboxResult.not_run("service", f"no result from the sandbox: {exc}")
    finally:
        writer.close()
    if result.isolation != "service":
        return SandboxResult.not_run(
            "service", "the service reported another isolation"
        )
    return result
