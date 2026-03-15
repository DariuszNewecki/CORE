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
import signal
from typing import Any

import typer

from shared.cli_utils import async_command
from shared.logger import getLogger


logger = getLogger(__name__)

daemon_app = typer.Typer(help="Background worker daemon management.")


@daemon_app.command("start")
@async_command
# ID: f3d2e3cd-7e95-473a-89d8-4af5438490ea
async def start() -> None:
    """
    Start all self-scheduling background workers.

    Keeps the process alive until SIGTERM or SIGINT. Add additional
    self-scheduling workers inside _run_daemon() as they are implemented.
    """
    await _run_daemon()


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
async def _run_daemon() -> None:
    """
    Async entry point. Starts all worker loops as asyncio tasks and
    waits for shutdown signal.
    """
    from will.workers.blackboard_auditor import BlackboardAuditor
    from will.workers.observer_worker import ObserverWorker
    from will.workers.repo_crawler import RepoCrawlerWorker
    from will.workers.repo_embedder import RepoEmbedderWorker
    from will.workers.worker_auditor import WorkerAuditor

    logger.info("CORE daemon starting...")

    observer = ObserverWorker()
    worker_auditor = WorkerAuditor()
    blackboard_auditor = BlackboardAuditor()
    repo_crawler = RepoCrawlerWorker()
    repo_embedder = (
        RepoEmbedderWorker()
    )  # self-initializes CognitiveService in run_loop

    tasks: list[asyncio.Task[Any]] = [
        asyncio.create_task(observer.run_loop(), name="observer_worker"),
        asyncio.create_task(worker_auditor.run_loop(), name="worker_auditor"),
        asyncio.create_task(blackboard_auditor.run_loop(), name="blackboard_auditor"),
        asyncio.create_task(repo_crawler.run_loop(), name="repo_crawler"),
        asyncio.create_task(repo_embedder.run_loop(), name="repo_embedder"),
    ]

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
