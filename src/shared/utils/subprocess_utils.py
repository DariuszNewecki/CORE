# src/shared/utils/subprocess_utils.py
"""
Provides shared utilities for running external commands as subprocesses.
Includes both sync and async variants to support the full CLI lifecycle.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.exceptions import CoreError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cfb6141b-6fe5-44c9-9819-cf2cab84d06d
class SubprocessCommandError(CoreError):
    """Raised when subprocess command execution fails."""


@dataclass
# ID: 6f1059a4-bacb-429d-b205-01eeb3cb38e1
class SubprocessResult:
    """Standardized result for async subprocess calls."""

    stdout: str
    stderr: str
    returncode: int


# ID: a83abb8d-b9c6-45f1-bf2c-e01b62420ebf
async def run_command_async(
    args: list[str], cwd: Path | str | None = None
) -> SubprocessResult:
    """
    Executes a shell command asynchronously.
    Required for non-blocking UI and Agent interactions.
    """
    logger.debug("Async Exec: %s", " ".join(args))

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )

    stdout, stderr = await process.communicate()

    return SubprocessResult(
        stdout=stdout.decode().strip(),
        stderr=stderr.decode().strip(),
        returncode=process.returncode or 0,
    )


# ID: f555860f-aeb3-4a20-92ff-eee51b7f4501
def run_poetry_command(
    description: str,
    command: list[str],
    cwd: Path | str | None = None,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> SubprocessResult:
    """Helper to run a command via Poetry, log it, and handle errors (Synchronous).

    ``cwd`` (#638 / ADR-106): when supplied, the subprocess runs in that
    directory rather than the daemon's process cwd. Fix actions executing
    inside a hermetic flow worktree pass the scoped ``repo_path`` here so
    external tools (ruff) operate on the sandbox tree, not the real one.
    Default ``None`` preserves the legacy process-cwd behaviour for the
    CLI/audit callers that run against the working tree directly.

    ``allowed_returncodes`` (#660): the exit codes that count as success.
    Many wrapped tools use a non-zero exit to report *findings*, not execution
    failure — ruff returns ``1`` for "would reformat" / lint findings /
    residual unfixable issues, reserving ``2`` for a genuine tool error. A
    caller wrapping such a tool passes the informative codes (e.g. ``(0, 1)``)
    so a findings result is not misreported as a command failure. The previous
    blanket ``check=True`` conflated the two and surfaced every formattable
    file as ``"poetry command failed."`` (#660).

    A disallowed exit raises ``SubprocessCommandError`` carrying the captured
    stderr/stdout, so the failure is diagnosable from the persisted
    ``ActionResult`` rather than only the ephemeral daemon log.

    Returns:
        SubprocessResult with the command's returncode and captured streams.
    """
    POETRY_EXECUTABLE = shutil.which("poetry")
    if not POETRY_EXECUTABLE:
        logger.error("❌ Could not find 'poetry' executable in your PATH.")
        raise SubprocessCommandError("poetry executable not found.", exit_code=1)

    logger.info(description)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    result = subprocess.run(
        full_command,
        check=False,
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )
    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.warning(result.stderr)

    if result.returncode not in allowed_returncodes:
        logger.error(
            "❌ Command failed (exit %s): %s",
            result.returncode,
            " ".join(full_command),
        )
        detail = (result.stderr or result.stdout or "").strip()
        raise SubprocessCommandError(
            f"poetry command failed (exit {result.returncode}): {' '.join(command)}"
            + (f" — {detail}" if detail else ""),
            exit_code=result.returncode or 1,
        )

    return SubprocessResult(
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode or 0,
    )


# ID: b58e3f7a-c12d-4856-9430-7d9e2c5a8b46
def run_systemctl(*args: str) -> SubprocessResult:
    """Run ``systemctl --user <args...>`` and return a typed SubprocessResult.

    Sanctuary entry point for systemctl invocations per ADR-081 D6: CORE
    delegates daemon-lifecycle (start/stop/restart) and service-inspection
    (is-active, show) to systemd. Routing every systemctl call through this
    helper keeps the dangerous-primitive surface confined to this module
    (already exempted under governance.dangerous_execution_primitives) and
    gives the rule's enforcement a single typed surface to track.
    """
    cmd = ["systemctl", "--user", *args]
    logger.debug("Sync Exec: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    return SubprocessResult(
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
        returncode=result.returncode,
    )


# ID: e74f1c9d-3a52-4837-b6c0-5f1a2d8e7c39
def list_all_processes(format_spec: str) -> str:
    """Run ``ps -eo <format_spec>`` and return the raw stdout.

    Sanctuary entry point for ps invocations against the full process
    table. Used by daemon-status stray-scan to detect orphan python
    processes systemd doesn't own. format_spec is the ``-o`` option's
    column list (e.g. ``"pid,ppid,lstart,cmd"``); raw output is returned
    so the caller can parse the column layout it requested.
    """
    cmd = ["ps", "-eo", format_spec]
    logger.debug("Sync Exec: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


# ID: 63ffc8b0-fd1e-4324-9b1b-f546eb094e3d
async def run_child_process(
    args: list[str], *, cwd: Path, env: dict[str, str]
) -> int:
    """Spawn a child process with inherited stdio and an explicit, non-merged environment.

    Sanctuary primitive for ADR-155 D5: the isolated demo's scenario process
    must be re-rooted with run-specific configuration (disposable DB/Qdrant
    endpoints, state dir) and must never inherit the invoking process's live
    ``.env`` — ``env`` is the complete environment for the child; nothing is
    merged from ``os.environ``. stdio is inherited (not captured) so a
    long-running scenario process streams its own output directly. No shell.
    """
    logger.debug("Child process exec: %s (cwd=%s)", " ".join(args), cwd)
    process = await asyncio.create_subprocess_exec(*args, cwd=str(cwd), env=env)
    return await process.wait()


# ID: 25e23e37-5aad-4aa0-8ea0-7c179791fe68
def compose_up_command(project_name: str, compose_file: Path) -> list[str]:
    """Build a `docker compose up -d --wait` command for a disposable project.

    Fixed shape (ADR-155 D4): `-d` detaches, `--wait` blocks until Compose's
    own health checks pass before returning, so the caller does not need a
    separate polling loop for the common case.
    """
    return [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        str(compose_file),
        "up",
        "-d",
        "--wait",
    ]


# ID: dcd817d2-a36f-430f-a335-c4ef2eea0481
def compose_down_command(project_name: str, compose_file: Path) -> list[str]:
    """Build a `docker compose down --volumes --remove-orphans` command.

    Always removes volumes and orphaned containers (ADR-155 D4/D11) — the
    project's infrastructure is disposable by design; nothing it creates
    should outlive the run.
    """
    return [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        str(compose_file),
        "down",
        "--volumes",
        "--remove-orphans",
    ]


# ID: 432d3064-e22f-4381-8df4-f82a9d756a1d
def compose_ps_command(project_name: str, compose_file: Path) -> list[str]:
    """Build a `docker compose ps --format json` command for health polling."""
    return [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        str(compose_file),
        "ps",
        "--format",
        "json",
    ]


# ID: 0d099164-bdbe-45a0-82aa-ff23b1794ff4
def compose_logs_command(project_name: str, compose_file: Path) -> list[str]:
    """Build a `docker compose logs` command for post-failure diagnostics."""
    return [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        str(compose_file),
        "logs",
    ]


# ID: c9627c6e-a3e7-449c-9e28-ee9f4b95d848
async def run_compose_command(
    args: list[str], *, cwd: Path, env: dict[str, str]
) -> SubprocessResult:
    """Execute a `docker compose` command built by the `compose_*_command` builders.

    Distinct from `run_child_process` (D5): a Compose invocation is an
    orchestration/diagnostic step whose output the caller inspects
    programmatically (health JSON from `ps`, log text after a failure) —
    output is captured here, not inherited.
    """
    logger.debug("Compose exec: %s (cwd=%s)", " ".join(args), cwd)
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return SubprocessResult(
        stdout=stdout.decode().strip(),
        stderr=stderr.decode().strip(),
        returncode=process.returncode or 0,
    )


# ID: 3797bae4-956b-4af1-9b67-c626709244d9
async def run_vulture(
    target: str, repo_root: Path | str, confidence: int = 80
) -> SubprocessResult:
    """Run ``vulture <target> --min-confidence <confidence>`` and return the result.

    Sanctuary entry point for vulture invocations, mirroring run_systemctl
    and list_all_processes. Issue #585: the prior implementation called
    asyncio.create_subprocess_exec directly from src/mind/logic/engines/
    workflow_gate/checks/dead_code.py, which placed subprocess semantics
    inside the Mind layer (architecture.layers.no_mind_execution +
    governance.dangerous_execution_primitives). Routing through this
    sanctuary confines the dangerous-primitive surface to shared/utils/
    (already exempted under the governance rule) and leaves dead_code.py
    free of subprocess imports.
    """
    cmd = ["vulture", target, "--min-confidence", str(confidence)]
    return await run_command_async(cmd, cwd=repo_root)
