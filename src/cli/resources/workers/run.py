# src/cli/resources/workers/run.py
"""Worker run command — starts a constitutional worker by declaration name."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from shared.cli_utils.decorators import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)

workers_app = typer.Typer(
    help="Constitutional worker management.",
    no_args_is_help=True,
)


def _load_worker_declarations() -> dict[str, dict]:
    """
    Discover all active worker declarations from .intent/workers/.

    Returns a dict keyed by declaration name (YAML stem), value is the
    parsed declaration dict. Only active workers are included.

    This is the constitutional alternative to a hardcoded Python registry —
    adding a new worker requires only a YAML declaration, not a code change.
    """
    workers_dir: Path = settings.MIND / "workers"
    if not workers_dir.exists():
        return {}

    declarations = {}
    for yaml_path in sorted(workers_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if data.get("metadata", {}).get("status") != "active":
                continue
            impl = data.get("implementation")
            if not impl or not impl.get("module") or not impl.get("class"):
                logger.warning(
                    "Worker declaration '%s' is missing implementation block — skipped.",
                    yaml_path.stem,
                )
                continue
            declarations[yaml_path.stem] = data
        except Exception as e:
            logger.warning("Could not load worker declaration %s: %s", yaml_path, e)

    return declarations


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

    declarations = _load_worker_declarations()

    if worker_name not in declarations:
        available = ", ".join(sorted(declarations.keys())) or "(none declared)"
        console.print(f"[red]Unknown worker: {worker_name}[/red]")
        console.print(f"Available: {available}")
        raise typer.Exit(code=1)

    declaration = declarations[worker_name]
    impl = declaration["implementation"]
    module_path: str = impl["module"]
    class_name: str = impl["class"]
    needs_context: bool = impl.get("requires_core_context", False)

    core_context: CoreContext = ctx.obj

    # Initialize cognitive service — required by sensing workers
    async with get_session() as session:
        await core_context.cognitive_service.initialize(session)

    module = importlib.import_module(module_path)
    worker_class = getattr(module, class_name)

    if needs_context:
        worker = worker_class(core_context=core_context)
    else:
        worker = worker_class(cognitive_service=core_context.cognitive_service)

    console.print(f"[bold green]Starting worker: {worker_name}[/bold green]")

    await worker.start()

    console.print(f"[bold green]Worker {worker_name} completed.[/bold green]")
