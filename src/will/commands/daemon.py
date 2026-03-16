# src/will/commands/daemon.py
# ID: will.commands.daemon
"""
Daemon Command - Background Worker Lifecycle Management.

Provides CLI entry points for starting and stopping long-running background
workers. Sanctuary (bootstrap) calls `start` once on system initialisation.

Constitutional standing:
- This module IS the activation boundary for self-scheduling workers.
- Workers started here manage their own asyncio loops via run_loop().
- This module does not schedule — it starts and monitors.

LAYER: will/commands — orchestration boundary.
"""

from __future__ import annotations

import asyncio
import importlib
import signal
from typing import Any

import typer

from shared.cli_utils import async_command
from shared.logger import getLogger


logger = getLogger(__name__)

daemon_app = typer.Typer(help="Background worker daemon management.")

# Default interval for one-shot workers that lack run_loop (seconds).
_ONE_SHOT_INTERVAL = 300


async def _run_one_shot_loop(worker: Any, stem: str, interval: int) -> None:
    """
    Wraps a one-shot worker (has start() but no run_loop()) in a periodic loop.
    Re-instantiation is not needed — start() is idempotent per the Worker contract.
    """
    logger.info("CORE daemon: one-shot loop for '%s' (interval=%ds)", stem, interval)
    while True:
        try:
            await worker.start()
        except Exception as e:
            logger.error(
                "CORE daemon: one-shot worker '%s' failed: %s", stem, e, exc_info=True
            )
        await asyncio.sleep(interval)


@daemon_app.command("start")
@async_command
# ID: f3d2e3cd-7e95-473a-89d8-4af5438490ea
async def start() -> None:
    """
    Start all self-scheduling background workers.

    Discovers workers dynamically from .intent/workers/*.yaml — no manual
    registration required. Keeps the process alive until SIGTERM or SIGINT.
    """
    await _run_daemon()


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
async def _run_daemon() -> None:
    """
    Async entry point. Discovers all active workers from .intent/workers/,
    instantiates each one, starts their run_loop (or one-shot loop) as
    asyncio tasks, and waits for shutdown signal.

    Constructor kwargs are resolved from the declaration:
    - requires_core_context → passes core_context=ctx
    - mandate.scope.rule_namespace → passes rule_namespace=<value>
    - declaration stem → always passed as declaration_name=<stem>
      so one worker class can back multiple namespace declarations.
    """
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

    from shared.infrastructure.git_service import GitService

    try:
        ctx.git_service = GitService(repo_path=BootstrapRegistry.get_repo_path())
    except Exception as e:
        logger.warning("CORE daemon: GitService unavailable: %s", e)

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

            # Resolve optional kwargs declared in the YAML
            rule_namespace = (
                declaration.get("mandate", {})
                .get("scope", {})
                .get("rule_namespace", "")
            )

            module = importlib.import_module(module_path)
            WorkerClass = getattr(module, class_name)

            # declaration_name always passed so one class can back
            # multiple namespace declarations with distinct UUIDs.
            kwargs: dict[str, Any] = {"declaration_name": stem}
            if rule_namespace:
                kwargs["rule_namespace"] = rule_namespace

            if requires_ctx:
                worker = WorkerClass(core_context=ctx, **kwargs)
            else:
                try:
                    worker = WorkerClass(**kwargs)
                except TypeError:
                    if cog_svc is None:
                        logger.warning(
                            "CORE daemon: skipping '%s' — needs CognitiveService but unavailable",
                            stem,
                        )
                        continue
                    worker = WorkerClass(cognitive_service=cog_svc, **kwargs)

            # Use run_loop() if the worker defines it; otherwise wrap start() in a loop.
            if hasattr(worker, "run_loop"):
                coro = worker.run_loop()
            else:
                interval = (
                    declaration.get("mandate", {})
                    .get("schedule", {})
                    .get("max_interval", _ONE_SHOT_INTERVAL)
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
