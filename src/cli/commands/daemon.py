# src/cli/commands/daemon.py
"""
Daemon Command - Background Worker Lifecycle Management.

Provides CLI entry points for starting long-running background workers.
Sanctuary (bootstrap) calls `start` once on system initialisation; systemd
invokes `core-admin daemon start` as the entry for `core-daemon.service`.

Constitutional standing:
- This module IS the activation boundary for self-scheduling workers.
- Workers started here manage their own asyncio loops via run_loop().
- This module does not schedule — it starts and monitors.

LAYER: cli/commands — CLI entry point for Will orchestration.

Bootstrap path — the `start` command and `_run_daemon` import body/shared
directly because this is what systemd executes to bring the daemon (and
therefore the API) into existence. A thin-client implementation would be
a chicken-and-egg deadlock — the daemon must be running for
/v1/daemon/start to be reachable. Per ADR-058 D3, the API's
POST /v1/daemon/start (operator-triggered remote restart) and this CLI's
`daemon start` (systemd-triggered bootstrap) are deliberately separate
paths.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import importlib
import logging
import os
import re
import signal
import socket
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

# Bootstrap imports — see module docstring.
from cli.utils import async_command
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import list_all_processes, run_systemctl


logger = getLogger(__name__)
console = Console()

daemon_app = typer.Typer(help="Background worker daemon management.")

# Default interval for one-shot workers that lack run_loop (seconds).
_CFG = load_operational_config().daemon

# Cold-start jitter cap (#611). Each one-shot worker delays its first cycle
# by a hash-of-stem offset in [0, _STARTUP_JITTER_CAP_SEC). Spreads the
# post-restart CPU peak across the cap window so a cohort of audit sensors
# can't blackout the single-worker uvicorn API.
_STARTUP_JITTER_CAP_SEC = 30

# Singleton-instance machinery.
# var/run/core-daemon.pid holds the PID of the running daemon; an exclusive
# fcntl lock on the same fd is the actual mutex (the file's contents are
# advisory — kernel-released flock is the source of truth, so crashes never
# leave stale locks).
# ADR-081 Step 2c — the unit list is computed dynamically (see _systemd_units).
# Base set always present.
_SYSTEMD_BASE_UNITS = ("core-daemon", "core-api")

# Match core-daemon-worker@<stem>.service or shortened core-daemon-worker@<stem>.
_TEMPLATE_UNIT_RE = re.compile(r"core-daemon-worker@([^.\s]+)(?:\.service)?")


# ID: 7c0c1eef-3a86-4f0b-86f1-e84f81e2a4fa
def _heavy_worker_stems() -> list[str]:
    """Stems of active workers declaring requires_dedicated_process: true.

    Source of truth for which dedicated daemons systemd is expected to host
    (ADR-081 D6). Reads .intent/workers/*.yaml each call so the wrappers
    pick up YAML changes without a CLI restart. Sorted for deterministic
    output.
    """
    import yaml

    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    workers_dir = BootstrapRegistry.get_repo_path() / ".intent" / "workers"
    stems: list[str] = []
    for f in sorted(workers_dir.glob("*.yaml")):
        try:
            decl = yaml.safe_load(f.read_text()) or {}
        except Exception:
            continue
        if decl.get("metadata", {}).get("status") != "active":
            continue
        if decl.get("implementation", {}).get("requires_dedicated_process"):
            stems.append(f.stem)
    return stems


# ID: 4d2f15a9-9e4c-4c3e-bf2a-7e0b30c7da11
def _systemd_units() -> list[str]:
    """Full systemd unit list this CLI manages (ADR-081 D6).

    Lightweight core-daemon + core-api + one core-daemon-worker@<stem>.service
    per active worker declaring requires_dedicated_process: true. Order is
    base units first, then dedicated units in stem-sorted order.
    """
    units = list(_SYSTEMD_BASE_UNITS)
    units.extend(f"core-daemon-worker@{s}.service" for s in _heavy_worker_stems())
    return units


# ID: 8a3b1c4d-6e7f-4a2b-9c1d-5e2f3a4b5c6d
def _enabled_template_stems() -> set[str]:
    """Stems of currently-enabled core-daemon-worker@<stem>.service instances.

    Used by `daemon status` to surface drift between .intent/workers/ state
    and systemd-enabled state (ADR-081 D6). Best-effort — returns an empty
    set if the wants directory is missing, so drift detection degrades to
    silent rather than blocking the status command.

    Probes the user-systemd wants directory directly because
    ``systemctl --user list-unit-files --state=enabled`` enumerates only
    the template unit file itself, not its enabled instances. The enabled
    instances live as symlinks under ``~/.config/systemd/user/default.target.wants/``
    (the canonical user-systemd location), so listing those is the source
    of truth.
    """
    wants_dir = Path.home() / ".config" / "systemd" / "user" / "default.target.wants"
    if not wants_dir.is_dir():
        return set()
    stems: set[str] = set()
    try:
        for entry in wants_dir.glob("core-daemon-worker@*.service"):
            m = _TEMPLATE_UNIT_RE.match(entry.name)
            if m:
                stems.add(m.group(1))
    except OSError:
        return set()
    return stems


# ID: 0b1ce63d-8b46-4d8b-b1d7-2c5b6a93e0a9
def _pid_file_for(only: str | None, repo_root: Path = Path(".")) -> Path:
    """Repo-relative PID file path for this daemon invocation.

    Default mode (``only is None``): the lightweight core-daemon PID file.
    Dedicated mode (``--only <stem>``): a per-stem PID file under
    ``var/run/core-daemon-worker-<stem>.pid``. Per-stem files mean an
    operator can run the lightweight daemon and one or more dedicated
    daemons simultaneously without lock contention. Per ADR-081 D4.
    """
    run_dir = PathResolver(repo_root).run_dir
    if only is None:
        return run_dir / "core-daemon.pid"
    return run_dir / f"core-daemon-worker-{only}.pid"


async def _run_one_shot_loop(worker: Any, stem: str, interval: int) -> None:
    """
    Wraps a one-shot worker (has start() but no run_loop()) in a periodic loop.
    Re-instantiation is not needed — start() is idempotent per the Worker contract.

    Cold-start jitter (#611): before the first cycle, each one-shot worker
    waits a deterministic offset in [0, _STARTUP_JITTER_CAP_SEC) computed
    from the stem's SHA-256 hash. Spreads simultaneous post-restart CPU
    draw across the cap window so a cohort of audit sensors can't blackout
    the single-worker uvicorn API for the first 2-5 minutes after restart.
    """
    import time

    logger.info("CORE daemon: one-shot loop for '%s' (interval=%ds)", stem, interval)

    jitter_cap = min(_STARTUP_JITTER_CAP_SEC, max(interval, 0))
    if jitter_cap > 0:
        offset = (
            int.from_bytes(hashlib.sha256(stem.encode()).digest()[:2], "big")
            % jitter_cap
        )
        if offset:
            logger.info("CORE daemon: '%s' staggered cold-start +%ds", stem, offset)
            await asyncio.sleep(offset)

    while True:
        cycle_start = time.monotonic()
        try:
            await worker.start()
        except Exception as e:
            logger.error(
                "CORE daemon: one-shot worker '%s' failed: %s", stem, e, exc_info=True
            )
        elapsed = time.monotonic() - cycle_start
        # Cycle-cap arithmetic per ADR-103: next cycle starts at max(elapsed, interval).
        await asyncio.sleep(max(interval - elapsed, 0))


@daemon_app.command("start")
@async_command
# ID: f3d2e3cd-7e95-473a-89d8-4af5438490ea
async def start(
    only: str | None = typer.Option(
        None,
        "--only",
        help=(
            "Run exactly one worker declared requires_dedicated_process: true, "
            "alone in its own asyncio loop. Stem is the .intent/workers/<stem>.yaml "
            "filename without extension. Without --only, the daemon excludes "
            "every worker with requires_dedicated_process: true and runs the "
            "remaining lightweight set. Per ADR-081 D5."
        ),
    ),
) -> None:
    """
    Start background workers (systemd entry point).

    Default mode (no ``--only``): discovers active workers dynamically from
    .intent/workers/*.yaml, excludes every worker that declares
    ``requires_dedicated_process: true``, and runs the lightweight set in a
    shared asyncio loop. This is the unit systemd starts as ``core-daemon``.

    Dedicated mode (``--only <stem>``): loads exactly that one worker and
    runs it alone in its own asyncio loop. The stem must be active and must
    declare ``requires_dedicated_process: true`` — refuses otherwise. This
    is the unit shape systemd starts as ``core-daemon-worker@<stem>.service``
    (template unit lands in Step 2c). Per ADR-081 D3 / D5.

    Each invocation acquires a singleton PID lock — default mode uses
    ``var/run/core-daemon.pid``; dedicated mode uses
    ``var/run/core-daemon-worker-<stem>.pid`` — so the lightweight daemon
    and N dedicated daemons can run simultaneously without contention.

    **Humans should use ``core-admin daemon up`` instead** — it goes
    through systemctl, returns immediately, and ensures the supervisor
    (not your shell) owns the process lifecycle.
    """
    await _run_daemon(only=only)


# ID: 3f1a9b7d-2c4e-4f85-a6d1-8e2b5c9f0a3d
def _daemon_reload() -> None:
    """Run ``systemctl --user daemon-reload`` so updated unit files take effect.

    Called before start and restart — harmless when unit files haven't
    changed, required when they have.
    """
    result = run_systemctl("daemon-reload")
    if result.returncode != 0:
        console.print(f"[yellow]daemon-reload warning: {result.stderr}[/yellow]")


# ID: eeac9460-6a08-45d1-8194-e77660355120
def _systemctl(verb: str) -> int:
    """Run ``systemctl --user <verb>`` against every CORE unit.

    The unit list is computed dynamically per ADR-081 D6 — lightweight
    core-daemon + core-api + one core-daemon-worker@<stem>.service instance
    per active worker declaring requires_dedicated_process: true.

    Delegates to ``shared.utils.subprocess_utils.run_systemctl`` — the
    dedicated sanctuary for systemctl invocations under
    ``governance.dangerous_execution_primitives``.
    """
    units = _systemd_units()
    result = run_systemctl(verb, *units)
    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(f"[yellow]{result.stderr}[/yellow]")
    return result.returncode


@daemon_app.command("up")
# ID: 6d9e21bf-a63d-4658-b7bb-a0cb470e7c49
def up() -> None:
    """Start all CORE units via systemd (the supported way).

    Covers core-daemon, core-api, and every enabled
    core-daemon-worker@<stem>.service instance (ADR-081 D6).
    """
    _daemon_reload()
    rc = _systemctl("start")
    if rc == 0:
        console.print("[green]CORE units up.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("down")
# ID: 7231666c-a6b8-4e71-8060-4447468f6b85
def down() -> None:
    """Stop all CORE units via systemd.

    Covers core-daemon, core-api, and every enabled
    core-daemon-worker@<stem>.service instance (ADR-081 D6).
    """
    rc = _systemctl("stop")
    if rc == 0:
        console.print("[green]CORE units down.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("restart")
# ID: e6b00ede-7cf5-4c02-b6b0-f2137a0ddecb
def restart() -> None:
    """Restart all CORE units via systemd.

    Covers core-daemon, core-api, and every enabled
    core-daemon-worker@<stem>.service instance (ADR-081 D6).
    """
    _daemon_reload()
    rc = _systemctl("restart")
    if rc == 0:
        console.print("[green]CORE units restarted.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("status")
# ID: ad62cbef-7f06-4d8e-9c3c-1b8d0f5a4c52
def status() -> None:
    """Show CORE service state and scan for stray (orphan) python processes.

    Unit list is dynamic per ADR-081 D6 — lightweight core-daemon + core-api
    plus one row per enabled core-daemon-worker@<stem>.service instance.
    Drift between .intent/workers/ classification and enabled systemd state
    is surfaced as a separate panel below the unit table.
    """
    table = Table(title="CORE services", show_header=True, header_style="bold")
    table.add_column("unit")
    table.add_column("active")
    table.add_column("MainPID")
    table.add_column("since")

    units = _systemd_units()
    systemd_pids: set[int] = set()
    for unit in units:
        is_active = run_systemctl("is-active", unit).stdout
        show = run_systemctl(
            "show", unit, "--property=MainPID,ActiveEnterTimestamp"
        ).stdout
        props = dict(
            line.split("=", 1) for line in show.strip().splitlines() if "=" in line
        )
        main_pid = props.get("MainPID", "0").strip()
        since = props.get("ActiveEnterTimestamp", "").strip() or "—"
        try:
            pid_int = int(main_pid)
            if pid_int > 0:
                systemd_pids.add(pid_int)
        except ValueError:
            pass
        color = "green" if is_active == "active" else "red"
        table.add_row(unit, f"[{color}]{is_active}[/{color}]", main_pid, since)

    console.print(table)

    # ADR-081 D6 — drift between .intent/workers/ classification and enabled
    # systemd state. Both directions are surfaced so operators can see when a
    # heavy YAML worker was added without enabling its template instance, or
    # when a stale template instance was left enabled after the YAML was
    # demoted / retired.
    expected_heavy = set(_heavy_worker_stems())
    enabled_templates = _enabled_template_stems()
    missing_enable = sorted(expected_heavy - enabled_templates)
    orphan_enable = sorted(enabled_templates - expected_heavy)
    if missing_enable or orphan_enable:
        console.print()
        drift_table = Table(
            title="ADR-081 worker / systemd drift",
            show_header=True,
            header_style="bold yellow",
        )
        drift_table.add_column("class")
        drift_table.add_column("stem")
        drift_table.add_column("remediation")
        for stem in missing_enable:
            drift_table.add_row(
                "[yellow]expected unit, not enabled[/yellow]",
                stem,
                f"systemctl --user enable --now core-daemon-worker@{stem}.service",
            )
        for stem in orphan_enable:
            drift_table.add_row(
                "[red]enabled unit, not in YAML[/red]",
                stem,
                f"systemctl --user disable --now core-daemon-worker@{stem}.service",
            )
        console.print(drift_table)

    # Stray scan: any python process under the repo venv that systemd doesn't
    # own. The orphan-daemon trap that motivated this command — a `daemon
    # start` whose shell exited and got adopted by PID 1 — shows up here.
    # Per ADR-081 D6, daemon invocations with `--only <stem>` for a known
    # heavy worker are recognised as legitimate even if systemd isn't tracking
    # their MainPID (e.g. governor ran a foreground daemon for testing).
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    venv_python = f"{BootstrapRegistry.get_repo_path()}/.venv/bin/python"
    ps = list_all_processes("pid,ppid,lstart,cmd")

    strays: list[str] = []
    skip_tokens = ("pytest", "ruff", "mypy", "core-admin daemon status")
    only_re = re.compile(r"--only\s+(\S+)")
    for line in ps.splitlines()[1:]:
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        cmd = parts[6]
        if venv_python not in cmd:
            continue
        if pid in systemd_pids or pid == os.getpid():
            continue
        if any(tok in cmd for tok in skip_tokens):
            continue
        # Recognise dedicated-worker daemons by their --only <stem> signature
        # when the stem is a known heavy worker. These are legitimate, not strays.
        m = only_re.search(cmd)
        if m and m.group(1) in expected_heavy:
            continue
        strays.append(line)

    if strays:
        console.print()
        console.print(
            "[red bold]Stray CORE python processes detected (not tracked by systemd):[/red bold]"
        )
        for line in strays:
            console.print(f"  {line}")
        console.print(
            "[yellow]Inspect with `ps -fp <pid>`; "
            "kill confirmed orphans with `kill -TERM <pid>`.[/yellow]"
        )
    else:
        console.print("[green]No stray CORE processes.[/green]")


def _instantiate_worker(
    WorkerClass: Any,
    kwargs: dict[str, Any],
    requires_ctx: bool,
    ctx: Any,
    cog_svc: Any,
    stem: str,
) -> Any | None:
    """
    Attempt to instantiate a worker with progressively simpler kwargs.

    Instantiation order:
    1. Full kwargs (declaration_name + rule_namespace + params + core_context/nothing)
    2. Standard kwargs only (declaration_name + rule_namespace, no extra params)
    3. Bare instantiation (no kwargs at all) — for workers with hardcoded
       declaration_name class attributes that predate the daemon kwarg contract
    4. Cognitive service fallback (for workers that need it but don't take core_context)

    Returns the instantiated worker, or None if all attempts fail.
    """
    standard_keys = {"declaration_name", "rule_namespace", "repo_root"}
    standard_kwargs = {k: v for k, v in kwargs.items() if k in standard_keys}

    attempts: list[tuple[str, Any]]

    if requires_ctx:
        attempts = [
            ("full + core_context", lambda: WorkerClass(core_context=ctx, **kwargs)),
            (
                "standard + core_context",
                lambda: WorkerClass(core_context=ctx, **standard_kwargs),
            ),
            ("bare + core_context", lambda: WorkerClass(core_context=ctx)),
        ]
    else:
        attempts = [
            ("full kwargs", lambda: WorkerClass(**kwargs)),
            ("standard kwargs", lambda: WorkerClass(**standard_kwargs)),
            ("bare", lambda: WorkerClass()),
        ]
        if cog_svc is not None:
            attempts.append(
                (
                    "cognitive_service",
                    lambda: WorkerClass(cognitive_service=cog_svc, **kwargs),
                )
            )

    for label, attempt in attempts:
        try:
            worker = attempt()
            if label != "full kwargs" and label != "full + core_context":
                logger.info(
                    "CORE daemon: '%s' instantiated via fallback '%s'.",
                    stem,
                    label,
                )
            return worker
        except TypeError:
            continue
        except Exception as exc:
            logger.error(
                "CORE daemon: '%s' instantiation failed unexpectedly (%s): %s",
                stem,
                label,
                exc,
                exc_info=True,
            )
            return None

    return None


# ID: c6908afb-8ab5-4df2-92eb-43896b3cfbc1
def _acquire_singleton_lock(pid_file_rel: Path) -> int:
    """Acquire exclusive flock on the daemon PID file.

    Returns the open file descriptor — caller MUST keep it open for the
    daemon's lifetime, since closing the fd releases the lock. On failure
    (another instance holds the lock), logs the holder PID and exits with
    code 1.

    ``pid_file_rel`` is repo-relative — caller passes ``_pid_file_for(only)``
    so default and dedicated daemons each acquire their own lock (ADR-081 D4).
    """
    from body.infrastructure.storage.file_handler import FileHandler
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    repo_path = BootstrapRegistry.get_repo_path()
    pid_file = repo_path / pid_file_rel
    FileHandler(str(repo_path)).ensure_dir(str(pid_file_rel.parent))
    fd = os.open(str(pid_file), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            with open(pid_file) as f:
                holder_pid = f.read().strip() or "<unknown>"
        except OSError:
            holder_pid = "<unknown>"
        os.close(fd)
        logger.error(
            "CORE daemon: another instance already running (PID %s, lock=%s). "
            "Use `core-admin daemon down` or `systemctl --user stop core-daemon core-api`.",
            holder_pid,
            pid_file,
        )
        sys.exit(1)
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.fsync(fd)
    logger.info(
        "CORE daemon: acquired singleton lock (%s, PID %d)", pid_file, os.getpid()
    )
    return fd


# ID: 00438b47-4d36-465d-ae6c-b512a4725be6
def _release_singleton_lock(fd: int, pid_file_rel: Path) -> None:
    """Release the singleton lock and unlink the PID file (both best-effort).

    ``pid_file_rel`` is repo-relative — caller passes the same value used at
    acquisition so the matching PID file is removed (ADR-081 D4).
    """
    from body.infrastructure.storage.file_handler import FileHandler
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    repo_path = BootstrapRegistry.get_repo_path()
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        FileHandler(str(repo_path)).remove_file(str(pid_file_rel))
    except OSError:
        pass


# ID: 3a7e9c1f-4b2d-4e8f-a5c6-7d8e9f0a1b2c
async def _watchdog_pinger() -> None:
    """Ping systemd watchdog at half the configured WatchdogSec interval.

    Systemd sets WATCHDOG_USEC when WatchdogSec is active. Without periodic
    sd_notify(WATCHDOG=1) the daemon is killed after WatchdogSec seconds —
    the root cause of the 131.5s restart cycle observed in ADR-081 telemetry.
    No-ops silently when WATCHDOG_USEC or NOTIFY_SOCKET are absent (not under
    a watchdog-enabled systemd unit).
    """
    usec_raw = os.environ.get("WATCHDOG_USEC")
    notify_path = os.environ.get("NOTIFY_SOCKET", "")
    if not usec_raw or not notify_path:
        return
    try:
        interval_sec = int(usec_raw) / 1_000_000 / 2
    except ValueError:
        return
    # Abstract sockets are prefixed with '@' in systemd; the kernel uses '\0'.
    sock_addr = ("\0" + notify_path[1:]) if notify_path.startswith("@") else notify_path
    logger.info(
        "CORE daemon: systemd watchdog pinger started (interval=%.1fs)",
        interval_sec,
    )
    while True:
        await asyncio.sleep(interval_sec)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.sendto(b"WATCHDOG=1", sock_addr)
        except OSError as exc:
            logger.warning("CORE daemon: watchdog ping failed: %s", exc)


# ID: ea1f2f3a-280e-4d88-a120-4b310a2ef31f
async def _run_daemon(only: str | None = None) -> None:
    """
    Async entry point. Discovers all active workers from .intent/workers/,
    instantiates each one, starts their run_loop (or one-shot loop) as
    asyncio tasks, and waits for shutdown signal.

    Constructor kwargs are resolved from the declaration in this order:
    1. declaration_name — always included (stem of the YAML file)
    2. rule_namespace   — from mandate.scope.rule_namespace if present
    3. core_context     — if implementation.requires_core_context is true
    4. implementation.params — arbitrary extra kwargs merged last

    Instantiation is tried with progressively simpler kwargs when TypeError
    occurs, so workers with hardcoded declaration_name class attributes and
    plain __init__(self) signatures are still started correctly.

    When ``only`` is set, runs exactly that one heavy worker (ADR-081 D3/D5)
    against a per-stem PID lock; otherwise excludes every heavy worker and
    runs the lightweight set against the default daemon PID lock.
    """
    pid_file_rel = _pid_file_for(only)
    lock_fd = _acquire_singleton_lock(pid_file_rel)
    try:
        await _run_daemon_locked(only=only)
    finally:
        _release_singleton_lock(lock_fd, pid_file_rel)


# ID: be19aae3-d399-4955-8ff7-f65aa5267aaf
async def _run_daemon_locked(only: str | None = None) -> None:
    """Body of _run_daemon, executed under the singleton lock.

    ``only`` mirrors the ``--only`` CLI flag (ADR-081 D5). When set, exactly
    one heavy worker is loaded; when None, every worker with
    ``requires_dedicated_process: true`` is excluded.
    """
    # Bootstrap-only imports — see _run_daemon docstring.
    import yaml

    from body.services.service_registry import service_registry
    from shared.context import CoreContext
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeService

    logger.info("CORE daemon starting...")

    # git_service, knowledge_service and file_handler are mandatory (#643) —
    # construct them up front so CoreContext is fully wired. These were already
    # wired unconditionally (no try/except) further down; moving them into the
    # constructor keeps the same fail-fast behaviour and satisfies the required
    # fields. The genuinely-degradable services (cognitive/qdrant/auditor) stay
    # post-construction in try/except below.
    from body.services.file_service import FileService
    from shared.infrastructure.git_service import GitService

    ctx = CoreContext(
        registry=service_registry,
        git_service=GitService(repo_path=BootstrapRegistry.get_repo_path()),
        knowledge_service=KnowledgeService(repo_path=BootstrapRegistry.get_repo_path()),
        file_handler=service_registry.get_file_handler(),
        file_service=FileService(BootstrapRegistry.get_repo_path()),
    )

    cog_svc: Any = None
    try:
        cog_svc = await service_registry.get_cognitive_service()
        ctx.cognitive_service = cog_svc
    except Exception as e:
        logger.warning(
            "CORE daemon: CognitiveService unavailable — workers requiring it will be skipped: %s",
            e,
        )

    try:
        ctx.qdrant_service = await service_registry.get_qdrant_service()
    except Exception as e:
        logger.warning("CORE daemon: QdrantService unavailable: %s", e)

    try:
        ctx.auditor_context = await service_registry.get_auditor_context()
    except Exception as e:
        logger.warning("CORE daemon: AuditorContext unavailable: %s", e)

    # ADR-071 D2.2 Phase 1: reclaim sandbox worktrees leaked by crashes.
    try:
        swept = ctx.git_service.sweep_orphan_worktrees()
        if swept:
            logger.info(
                "CORE daemon: cleared %d orphan action sandbox(es) from prior runs",
                swept,
            )
    except Exception as sweep_err:
        logger.warning(
            "CORE daemon: orphan worktree sweep failed (non-fatal): %s",
            sweep_err,
        )

    # ADR-081 Step 0 — loop-hold instrumentation (Option 1, permanent telemetry).
    # Gated on operational_config.daemon.set_debug. When enabled, the asyncio
    # event loop emits a `logger.warning` on the "asyncio" logger whenever a
    # single handle executes for longer than `slow_callback_duration`. Step 3a
    # subscribes a structured handler to those emissions; the warnings are the
    # only low-level loop-hold source CPython provides.
    loop = asyncio.get_running_loop()
    if _CFG.set_debug:
        loop.set_debug(True)
        loop.slow_callback_duration = _CFG.slow_callback_duration_sec
        logger.info(
            "CORE daemon: asyncio debug mode enabled "
            "(slow_callback_duration=%.3fs) — ADR-081 Step 0",
            _CFG.slow_callback_duration_sec,
        )

    workers_dir = BootstrapRegistry.get_repo_path() / ".intent" / "workers"

    # ADR-081 D5 — daemon discovery contract.
    # --only <stem>: load exactly that stem, must be active AND heavy.
    # --only absent: discover all active workers, exclude every heavy one.
    if only is not None:
        if "/" in only or ".." in only or only != Path(only).name:
            logger.error(
                "CORE daemon: --only stem %r contains path separators or "
                "traversal — refusing.",
                only,
            )
            return
        yaml_files = [workers_dir / f"{only}.yaml"]
        if not yaml_files[0].exists():
            logger.error(
                "CORE daemon: --only stem '%s' has no declaration at %s.",
                only,
                yaml_files[0],
            )
            return
        only_decl = yaml.safe_load(yaml_files[0].read_text())
        only_status = only_decl.get("metadata", {}).get("status", "")
        if only_status != "active":
            logger.error(
                "CORE daemon: --only stem '%s' is not active "
                "(metadata.status=%r). Refusing.",
                only,
                only_status,
            )
            return
        if not only_decl.get("implementation", {}).get(
            "requires_dedicated_process", False
        ):
            logger.error(
                "CORE daemon: --only stem '%s' declares "
                "requires_dedicated_process=false. Run it under the lightweight "
                "daemon via `core-admin daemon start` without --only.",
                only,
            )
            return
        logger.info(
            "CORE daemon: dedicated mode — running only '%s' "
            "(requires_dedicated_process: true).",
            only,
        )
    else:
        yaml_files = sorted(workers_dir.glob("*.yaml"))

    tasks: list[asyncio.Task[Any]] = []
    excluded_heavy: list[str] = []
    # ADR-081 Step 3a — stem → Worker registry for loop-hold telemetry
    # attribution. Populated alongside worker instantiation below; consumed
    # by the drain coroutine after the loop completes.
    workers_by_stem: dict[str, Any] = {}

    for yaml_file in yaml_files:
        stem = yaml_file.stem

        try:
            declaration = yaml.safe_load(yaml_file.read_text())

            status = declaration.get("metadata", {}).get("status", "")
            if status != "active":
                logger.debug("CORE daemon: skipping '%s' — status=%s", stem, status)
                continue

            impl = declaration.get("implementation", {})

            # ADR-081 D3 — in default mode, never host a worker that declares
            # requires_dedicated_process: true. Its dedicated systemd unit
            # runs it alone. --only mode passed the heavy-worker check above.
            if only is None and impl.get("requires_dedicated_process", False):
                excluded_heavy.append(stem)
                logger.info(
                    "CORE daemon: excluding heavy worker '%s' "
                    "(requires_dedicated_process: true) — runs in a dedicated daemon.",
                    stem,
                )
                continue
            module_path = impl["module"]
            class_name = impl["class"]
            requires_ctx = impl.get("requires_core_context", False)

            # Build constructor kwargs.
            # declaration_name is always included — enables one class to back
            # multiple namespace declarations with distinct UUIDs.
            # repo_root is always included so Worker._load_declaration bypasses the
            # CWD-dependent singleton and uses the daemon's authoritative repo path.
            kwargs: dict[str, Any] = {
                "declaration_name": stem,
                "repo_root": BootstrapRegistry.get_repo_path(),
            }

            rule_namespace = (
                declaration.get("mandate", {})
                .get("scope", {})
                .get("rule_namespace", "")
            )
            if rule_namespace:
                kwargs["rule_namespace"] = rule_namespace

            # implementation.params — arbitrary extra constructor kwargs.
            # Protected standard fields cannot be overridden via params.
            extra_params = impl.get("params") or {}
            if extra_params:
                protected = {
                    "declaration_name",
                    "rule_namespace",
                    "core_context",
                    "cognitive_service",
                    "repo_root",
                }
                clashes = set(extra_params) & protected
                if clashes:
                    logger.warning(
                        "CORE daemon: '%s' implementation.params contains protected "
                        "keys %s — they will be ignored.",
                        stem,
                        clashes,
                    )
                    extra_params = {
                        k: v for k, v in extra_params.items() if k not in protected
                    }
                kwargs.update(extra_params)

            module = importlib.import_module(module_path)
            WorkerClass = getattr(module, class_name)

            worker = _instantiate_worker(
                WorkerClass=WorkerClass,
                kwargs=kwargs,
                requires_ctx=requires_ctx,
                ctx=ctx,
                cog_svc=cog_svc,
                stem=stem,
            )

            if worker is None:
                logger.error(
                    "CORE daemon: could not instantiate '%s' — all attempts failed. "
                    "Worker will not be started.",
                    stem,
                )
                continue

            # Use run_loop() if the worker defines it; otherwise wrap start() in a loop.
            if hasattr(worker, "run_loop"):
                coro = worker.run_loop()
            else:
                interval = (
                    declaration.get("mandate", {})
                    .get("schedule", {})
                    .get("max_interval", _CFG.one_shot_interval_sec)
                )
                coro = _run_one_shot_loop(worker, stem, interval)

            task = asyncio.create_task(coro, name=f"{stem}_worker")
            tasks.append(task)
            workers_by_stem[stem] = worker
            logger.info(
                "CORE daemon: started worker '%s' (%s.%s)",
                stem,
                module_path,
                class_name,
            )

        except Exception as e:
            logger.error(
                "CORE daemon: failed to load worker '%s': %s",
                stem,
                e,
                exc_info=True,
            )

    logger.info("CORE daemon: %d worker(s) started.", len(tasks))
    if excluded_heavy:
        logger.info(
            "CORE daemon: excluded %d heavy worker(s) requiring dedicated "
            "processes (ADR-081 D3): %s",
            len(excluded_heavy),
            ", ".join(excluded_heavy),
        )

    # ADR-081 Step 3a-telemetry — install slow-callback blackboard handler
    # alongside the loop.set_debug(True) instrumentation from Step 0. The
    # handler runs in lockstep with asyncio's slow-callback warnings (only
    # emitted when set_debug is on), so it costs nothing when set_debug is
    # off and the drain task self-cancels on shutdown.
    telemetry_task: asyncio.Task[Any] | None = None
    telemetry_handler: logging.Handler | None = None
    if _CFG.set_debug and workers_by_stem:
        from shared.workers.loop_hold_telemetry import (
            SlowCallbackBlackboardHandler,
            drain_loop_hold_samples,
            make_sample_queue,
        )

        sample_queue = make_sample_queue()
        telemetry_handler = SlowCallbackBlackboardHandler(sample_queue)
        logging.getLogger("asyncio").addHandler(telemetry_handler)
        telemetry_task = asyncio.create_task(
            drain_loop_hold_samples(sample_queue, workers_by_stem),
            name="loop_hold_telemetry_drain",
        )
        logger.info(
            "CORE daemon: loop-hold telemetry handler installed "
            "(ADR-081 Step 3a) — %d worker(s) registered for attribution.",
            len(workers_by_stem),
        )

    # Systemd watchdog pinger — must be started before stop_event.wait() so it
    # keeps pinging for the full daemon lifetime (ADR-081; see _watchdog_pinger).
    watchdog_task: asyncio.Task[None] = asyncio.create_task(
        _watchdog_pinger(), name="watchdog_pinger"
    )

    # loop is acquired above (ADR-081 Step 0); reuse it for signal handling.
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("CORE daemon: shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()

    logger.info("CORE daemon: cancelling workers...")
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    # ADR-081 Step 3a — tear down telemetry after the worker tasks have
    # finished cancelling. Removing the handler first stops further
    # samples landing in the queue; cancelling the drain task lets it
    # exit cleanly via its CancelledError handler.
    if telemetry_handler is not None:
        logging.getLogger("asyncio").removeHandler(telemetry_handler)
    if telemetry_task is not None:
        telemetry_task.cancel()
        try:
            await telemetry_task
        except asyncio.CancelledError:
            pass

    watchdog_task.cancel()
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass

    logger.info("CORE daemon: stopped cleanly.")
