# src/cli/resources/workers/run.py
"""Worker run command — starts a constitutional worker by declaration name."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console

from cli.utils.decorators import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session


logger = logging.getLogger(__name__)
console = Console()
workers_app = typer.Typer(
    help="Constitutional worker management.", no_args_is_help=True
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
            if not impl or not impl.get("module") or (not impl.get("class")):
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
# ID: ed6afc60-992e-4695-9a64-59844ec6be65
async def workers_run_cmd(
    ctx: typer.Context,
    worker_name: str = typer.Argument(
        ..., help="Worker declaration name (e.g. doc_worker)."
    ),
) -> None:
    """Start a constitutional worker by its declaration name."""
    import importlib

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
    async with get_session() as session:
        await core_context.cognitive_service.initialize(session)
    module = importlib.import_module(module_path)
    worker_class = getattr(module, class_name)

    # Replicate the daemon's constructor-kwargs build (see _run_daemon in
    # cli/commands/daemon.py) so parameterised workers — those declaring
    # mandate.scope.rule_namespace or implementation.params — receive the
    # same arguments they get under the daemon. Without this, sensors like
    # AuditViolationSensor TypeError on missing rule_namespace (#262).
    kwargs: dict[str, Any] = {"declaration_name": worker_name}
    rule_namespace = (
        declaration.get("mandate", {}).get("scope", {}).get("rule_namespace", "")
    )
    if rule_namespace:
        kwargs["rule_namespace"] = rule_namespace

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
                "Worker '%s' implementation.params contains protected keys "
                "%s — they will be ignored.",
                worker_name,
                clashes,
            )
            extra_params = {k: v for k, v in extra_params.items() if k not in protected}
        kwargs.update(extra_params)

    cog_svc = core_context.cognitive_service

    # Single fallback to bare instantiation handles legacy workers whose
    # __init__ takes no args and rely on a class-level declaration_name
    # (e.g. ObserverWorker). Anything more elaborate belongs in the daemon's
    # _instantiate_worker, not the CLI run path.
    if needs_context:
        try:
            worker = worker_class(core_context=core_context, **kwargs)
        except TypeError:
            worker = worker_class(core_context=core_context)
    else:
        try:
            worker = worker_class(cognitive_service=cog_svc, **kwargs)
        except TypeError:
            worker = worker_class()

    if not worker.declaration_name:
        worker.declaration_name = worker_name
    console.print(f"[bold green]Starting worker: {worker_name}[/bold green]")
    await worker.start()
    console.print(f"[bold green]Worker {worker_name} completed.[/bold green]")
