# src/cli/resources/workers/run.py
"""Worker run command — starts a constitutional worker by declaration name."""

from __future__ import annotations

import typer

from shared.cli_utils.decorators import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)

workers_app = typer.Typer(
    help="Constitutional worker management.",
    no_args_is_help=True,
)

# Registry of available workers — extend as new workers are declared
# Format: "name": "module.path.ClassName"
_WORKER_REGISTRY: dict[str, tuple[str, str, bool]] = {
    # (module_path, class_name, requires_core_context)
    "doc_worker": ("will.workers.doc_worker", "DocWorker", False),
    "doc_writer": ("body.workers.doc_writer", "DocWriter", True),
}


@workers_app.command("run")
@core_command(dangerous=False)
# ID: f7a8b9c0-d1e2-3f4a-5b6c-7d8e9f0a1b2c
async def workers_run_cmd(
    ctx: typer.Context,
    worker_name: str = typer.Argument(
        ..., help="Worker declaration name (e.g. doc_worker)."
    ),
) -> None:
    """Start a constitutional worker by its declaration name."""
    import importlib

    from rich.console import Console

    console = Console()

    if worker_name not in _WORKER_REGISTRY:
        available = ", ".join(_WORKER_REGISTRY.keys())
        console.print(f"[red]Unknown worker: {worker_name}[/red]")
        console.print(f"Available: {available}")
        raise typer.Exit(code=1)

    core_context: CoreContext = ctx.obj

    # Initialize cognitive service — required by sensing workers
    async with get_session() as session:
        await core_context.cognitive_service.initialize(session)

    module_path, class_name, needs_context = _WORKER_REGISTRY[worker_name]
    module = importlib.import_module(module_path)
    worker_class = getattr(module, class_name)

    if needs_context:
        worker = worker_class(core_context=core_context)
    else:
        worker = worker_class(cognitive_service=core_context.cognitive_service)

    console.print(f"[bold green]Starting worker: {worker_name}[/bold green]")

    await worker.start()

    console.print(f"[bold green]Worker {worker_name} completed.[/bold green]")
