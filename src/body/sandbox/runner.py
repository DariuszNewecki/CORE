# src/body/sandbox/runner.py
"""
Run one sandbox job's bootstrap in a child process (ADR-132 D10.10).

Shared by both modes: the sandbox service calls it inside its unit instance
(as ``core-sandbox``), and the ``local`` mode calls it as the caller. The
child gets:

- ``stdin=/dev/null`` and no inherited descriptors except the report pipe,
  so it never holds the service's connection;
- an allow-listed environment (nothing copied from the parent);
- its own session, killed as a group on timeout. In the service, systemd's
  ``KillMode=control-group`` also reaps anything that left the group when
  the instance ends; in ``local`` mode a descendant that called ``setsid``
  can outlive the job (stated limit of ``local``).

Output is read up to a byte cap while it arrives; the rest is drained and
discarded, and the result says ``output_truncated``.

CONSTITUTIONAL ALIGNMENT:
- Starts repository code on purpose: this module and the bootstrap are the
  one sanctioned place that does (governance.dangerous_execution_primitives:
  justified, it is the sandbox).
"""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.sandbox.models import (
    AUDIT_KIND,
    COLLECT_KIND,
    SandboxJob,
    SandboxResult,
    classify_audit,
    classify_pytest,
)
from shared.logger import getLogger


logger = getLogger(__name__)

BOOTSTRAP = Path(__file__).with_name("bootstrap.py")
OUTPUT_CAP_BYTES = 1024 * 1024
REPORT_CAP_BYTES = 4 * 1024 * 1024
_KILL_GRACE_SEC = 5.0


# ID: 89488031-13a8-4e91-ab2b-28a04d0c536b
def child_environment(work_dir: Path) -> dict[str, str]:
    """The complete environment of a job child. Nothing comes from the parent."""
    venv_bin = str(Path(sys.executable).parent)
    return {
        "PATH": f"{venv_bin}:/usr/bin:/bin",
        "HOME": str(work_dir),
        "TMPDIR": str(work_dir),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CORE_ENV": "test",
        "LLM_ENABLED": "false",
        "LOG_LEVEL": "WARNING",
        # The audit's ruff and mypy keep their caches in the job's scratch:
        # the snapshot is read-only.
        "RUFF_CACHE_DIR": str(work_dir / ".ruff_cache"),
        "MYPY_CACHE_DIR": str(work_dir / ".mypy_cache"),
    }


@dataclass
class _Captured:
    stdout: bytes = b""
    stderr: bytes = b""
    report: bytes = b""
    truncated: bool = False


# ID: da7d4382-4110-4536-8077-b12c377e5732
def run_job(
    job: SandboxJob,
    *,
    snapshot_dir: Path,
    work_dir: Path,
    isolation: str,
    snapshot_sha256: str = "",
) -> SandboxResult:
    """Run *job* against *snapshot_dir*, writing only under *work_dir*."""
    started = time.monotonic()
    report_r, report_w = os.pipe()
    spec = {
        "snapshot": str(snapshot_dir),
        "targets": list(job.targets),
        "markers": job.effective_markers(),
        "exclude_integration": job.exclude_integration,
        "collect_only": job.kind == COLLECT_KIND,
        "coverage": job.coverage,
        "report_fd": report_w,
        "kind": job.kind,
        "audit_rules": list(job.audit_rules),
    }
    argv = [sys.executable, "-I", str(BOOTSTRAP), json.dumps(spec)]
    try:
        process = subprocess.Popen(
            argv,
            cwd=work_dir,
            env=child_environment(work_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(report_w,),
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        os.close(report_r)
        os.close(report_w)
        return SandboxResult.not_run(isolation, f"the job could not start: {exc}")
    os.close(report_w)

    captured, timed_out = _collect(process, report_r, job.timeout_sec)
    exit_code = process.returncode
    report = _parse_report(captured.report)
    if job.kind == AUDIT_KIND:
        status, completeness, reason = classify_audit(
            exit_code=exit_code, timed_out=timed_out, report=report
        )
    else:
        status, completeness, reason = classify_pytest(
            exit_code=exit_code,
            timed_out=timed_out,
            report=report,
            exclude_integration=job.exclude_integration,
            collect_only=job.kind == COLLECT_KIND,
        )
    return SandboxResult(
        status=status,
        completeness=completeness,
        isolation=isolation,
        reason=reason,
        exit_code=exit_code,
        counts=dict((report or {}).get("counts", {})),
        excluded=list((report or {}).get("excluded", [])),
        passed_ids=list((report or {}).get("passed_ids", [])),
        failed_ids=list((report or {}).get("failed_ids", [])),
        coverage=dict((report or {}).get("coverage", {})),
        audit=dict((report or {}).get("audit") or {}),
        stdout=captured.stdout.decode(errors="replace"),
        stderr=captured.stderr.decode(errors="replace"),
        output_truncated=captured.truncated,
        duration_sec=round(time.monotonic() - started, 3),
        snapshot_sha256=snapshot_sha256,
    )


def _collect(
    process: subprocess.Popen[bytes], report_fd: int, timeout_sec: int
) -> tuple[_Captured, bool]:
    captured = _Captured()
    deadline = time.monotonic() + timeout_sec
    timed_out = False
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    streams: dict[int, str] = {
        process.stdout.fileno(): "stdout",
        process.stderr.fileno(): "stderr",
        report_fd: "report",
    }
    for fd in streams:
        os.set_blocking(fd, False)
        selector.register(fd, selectors.EVENT_READ)
    exited_at: float | None = None
    try:
        while streams:
            now = time.monotonic()
            if exited_at is None and process.poll() is not None:
                exited_at = now
            if exited_at is not None and now - exited_at > _KILL_GRACE_SEC:
                break  # a descendant holds a pipe after the job ended
            remaining = deadline - now
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(timeout=min(remaining, 1.0)):
                fd = int(key.fd)
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(fd)
                    del streams[fd]
                    continue
                _append(captured, streams[fd], chunk)
        if not timed_out:
            try:
                process.wait(timeout=max(deadline - time.monotonic(), 0.1))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        _kill_group(process)  # the job is over: nothing it started may stay
        selector.close()
        os.close(report_fd)
        process.stdout.close()
        process.stderr.close()
    return captured, timed_out


def _append(captured: _Captured, stream: str, chunk: bytes) -> None:
    cap = REPORT_CAP_BYTES if stream == "report" else OUTPUT_CAP_BYTES
    current: bytes = getattr(captured, stream)
    room = cap - len(current)
    if room <= 0:
        captured.truncated = True
        return
    if len(chunk) > room:
        captured.truncated = True
        chunk = chunk[:room]
    setattr(captured, stream, current + chunk)


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    pid = process.pid
    if pid > 1 and pid != os.getpgrp():
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.wait(timeout=_KILL_GRACE_SEC)
    except subprocess.TimeoutExpired:
        logger.warning("sandbox job %s killed but not reaped", pid)


def _parse_report(raw: bytes) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return report if isinstance(report, dict) else None
