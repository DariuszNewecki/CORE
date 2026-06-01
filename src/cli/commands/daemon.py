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
import importlib
import os
import signal
import subprocess
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


logger = getLogger(__name__)
console = Console()

daemon_app = typer.Typer(help="Background worker daemon management.")

# Default interval for one-shot workers that lack run_loop (seconds).
_CFG = load_operational_config().daemon

# Singleton-instance machinery.
# var/run/core-daemon.pid holds the PID of the running daemon; an exclusive
# fcntl lock on the same fd is the actual mutex (the file's contents are
# advisory — kernel-released flock is the source of truth, so crashes never
# leave stale locks).
_PID_FILE_REL = Path("var/run/core-daemon.pid")
_SYSTEMD_UNITS = ("core-daemon", "core-api")


async def _run_one_shot_loop(worker: Any, stem: str, interval: int) -> None:
    """
    Wraps a one-shot worker (has start() but no run_loop()) in a periodic loop.
    Re-instantiation is not needed — start() is idempotent per the Worker contract.
    """
    import time

    logger.info("CORE daemon: one-shot loop for '%s' (interval=%ds)", stem, interval)
    while True:
        cycle_start = time.monotonic()
        try:
            await worker.start()
        except Exception as e:
            logger.error(
                "CORE daemon: one-shot worker '%s' failed: %s", stem, e, exc_info=True
            )
        elapsed = time.monotonic() - cycle_start
        await asyncio.sleep(max(interval - elapsed, 0))


@daemon_app.command("start")
@async_command
# ID: f3d2e3cd-7e95-473a-89d8-4af5438490ea
async def start() -> None:
    """
    Start all self-scheduling background workers (systemd entry point).

    Discovers workers dynamically from .intent/workers/*.yaml — no manual
    registration required. Keeps the process alive until SIGTERM or SIGINT.

    This is the long-running foreground process that systemd invokes via
    `ExecStart=...core-admin daemon start`. **Humans should use
    `core-admin daemon up` instead** — it goes through systemctl, returns
    immediately, and ensures the supervisor (not your shell) owns the
    process lifecycle. The PID-file lock here will refuse a second
    `daemon start` if one is already running, but the `up` path is the
    only one that registers with systemd in the first place.
    """
    await _run_daemon()


# ID: eeac9460-6a08-45d1-8194-e77660355120
def _systemctl(verb: str) -> int:
    """Run `systemctl --user <verb> core-daemon core-api` and stream output."""
    cmd = ["systemctl", "--user", verb, *_SYSTEMD_UNITS]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        console.print(result.stdout.rstrip())
    if result.stderr:
        console.print(f"[yellow]{result.stderr.rstrip()}[/yellow]")
    return result.returncode


@daemon_app.command("up")
# ID: 6d9e21bf-a63d-4658-b7bb-a0cb470e7c49
def up() -> None:
    """Start core-daemon + core-api via systemd (the supported way)."""
    rc = _systemctl("start")
    if rc == 0:
        console.print("[green]CORE daemon + API up.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("down")
# ID: 7231666c-a6b8-4e71-8060-4447468f6b85
def down() -> None:
    """Stop core-daemon + core-api via systemd."""
    rc = _systemctl("stop")
    if rc == 0:
        console.print("[green]CORE daemon + API down.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("restart")
# ID: e6b00ede-7cf5-4c02-b6b0-f2137a0ddecb
def restart() -> None:
    """Restart core-daemon + core-api via systemd."""
    rc = _systemctl("restart")
    if rc == 0:
        console.print("[green]CORE daemon + API restarted.[/green]")
    raise typer.Exit(code=rc)


@daemon_app.command("status")
# ID: ad62cbef-7f06-4d8e-9c3c-1b8d0f5a4c52
def status() -> None:
    """Show CORE service state and scan for stray (orphan) python processes."""
    table = Table(title="CORE services", show_header=True, header_style="bold")
    table.add_column("unit")
    table.add_column("active")
    table.add_column("MainPID")
    table.add_column("since")

    systemd_pids: set[int] = set()
    for unit in _SYSTEMD_UNITS:
        is_active = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
        ).stdout.strip()
        show = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=MainPID,ActiveEnterTimestamp",
            ],
            capture_output=True,
            text=True,
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

    # Stray scan: any python process under the repo venv that systemd doesn't
    # own. The orphan-daemon trap that motivated this command — a `daemon
    # start` whose shell exited and got adopted by PID 1 — shows up here.
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    venv_python = f"{BootstrapRegistry.get_repo_path()}/.venv/bin/python"
    ps = subprocess.run(
        ["ps", "-eo", "pid,ppid,lstart,cmd"],
        capture_output=True,
        text=True,
    ).stdout

    strays: list[str] = []
    skip_tokens = ("pytest", "ruff", "mypy", "core-admin daemon status")
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
    standard_keys = {"declaration_name", "rule_namespace"}
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
def _acquire_singleton_lock() -> int:
    """Acquire exclusive flock on the daemon PID file.

    Returns the open file descriptor — caller MUST keep it open for the
    daemon's lifetime, since closing the fd releases the lock. On failure
    (another instance holds the lock), logs the holder PID and exits with
    code 1.
    """
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    pid_file = BootstrapRegistry.get_repo_path() / _PID_FILE_REL
    pid_file.parent.mkdir(parents=True, exist_ok=True)
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
def _release_singleton_lock(fd: int) -> None:
    """Release the singleton lock and unlink the PID file (both best-effort)."""
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    pid_file = BootstrapRegistry.get_repo_path() / _PID_FILE_REL
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        pid_file.unlink()
    except OSError:
        pass


# ID: ea1f2f3a-280e-4d88-a120-4b310a2ef31f
async def _run_daemon() -> None:
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
    """
    lock_fd = _acquire_singleton_lock()
    try:
        await _run_daemon_locked()
    finally:
        _release_singleton_lock(lock_fd)


# ID: be19aae3-d399-4955-8ff7-f65aa5267aaf
async def _run_daemon_locked() -> None:
    """Body of _run_daemon, executed under the singleton lock."""
    # Bootstrap-only imports — see _run_daemon docstring.
    import yaml

    from body.services.service_registry import service_registry
    from shared.context import CoreContext
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeService

    logger.info("CORE daemon starting...")

    ctx = CoreContext(registry=service_registry)

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

    ctx.knowledge_service = KnowledgeService(
        repo_path=BootstrapRegistry.get_repo_path()
    )

    # Bootstrap-only — daemon constructs its own GitService (no API yet to call).
    from shared.infrastructure.git_service import GitService

    try:
        ctx.git_service = GitService(repo_path=BootstrapRegistry.get_repo_path())
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
    except Exception as e:
        logger.warning("CORE daemon: GitService unavailable: %s", e)

    ctx.file_handler = service_registry.get_file_handler()

    workers_dir = BootstrapRegistry.get_repo_path() / ".intent" / "workers"
    tasks: list[asyncio.Task[Any]] = []

    for yaml_file in sorted(workers_dir.glob("*.yaml")):
        stem = yaml_file.stem

        try:
            declaration = yaml.safe_load(yaml_file.read_text())

            status = declaration.get("metadata", {}).get("status", "")
            if status != "active":
                logger.debug("CORE daemon: skipping '%s' — status=%s", stem, status)
                continue

            impl = declaration.get("implementation", {})
            module_path = impl["module"]
            class_name = impl["class"]
            requires_ctx = impl.get("requires_core_context", False)

            # Build constructor kwargs.
            # declaration_name is always included — enables one class to back
            # multiple namespace declarations with distinct UUIDs.
            kwargs: dict[str, Any] = {"declaration_name": stem}

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

    loop = asyncio.get_running_loop()
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
    logger.info("CORE daemon: stopped cleanly.")
