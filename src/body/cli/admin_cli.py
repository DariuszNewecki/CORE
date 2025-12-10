# src/body/cli/admin_cli.py

"""
The single, canonical entry point for the core-admin CLI.
This module assembles all command groups into a single Typer application.

Refactored for A2 Autonomy: Now uses ServiceRegistry for dependency wiring.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.commands import (
    check,
    check_atomic_actions,
    check_patterns,
    coverage,
    enrich,
    fix,
    inspect,
    mind,
    run,
    search,
    secrets,
    submit,
)
from body.cli.commands.dev_sync import dev_sync_app
from body.cli.commands.develop import develop_app
from body.cli.commands.fix import fix_app
from body.cli.commands.inspect_patterns import inspect_patterns
from body.cli.commands.manage import manage
from body.cli.interactive import launch_interactive_menu
from body.cli.logic.tools import tools_app

# New Architecture: Registry
from body.services.service_registry import service_registry
from mind.enforcement import audit
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.context import cli as context_cli
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import PlannerConfig


console = Console()
logger = getLogger(__name__)

app = typer.Typer(
    name="core-admin",
    help=(
        "\n    CORE: The Self-Improving System Architect's Toolkit.\n"
        "    This CLI is the primary interface for operating and governing the CORE system.\n"
        "    "
    ),
    no_args_is_help=False,
)

# Initialize the Context using the Registry pattern.
# Note: We ONLY initialize what's strictly required for CLI bootstrap.
# All heavy lifting (Qdrant, Cognitive, Auditor) happens lazily via the registry.
core_context = CoreContext(
    registry=service_registry,
    # Legacy fields - populated for backward compatibility, but sourced from registry/settings
    # We still create simple lightweight objects here if needed, or pass None
    git_service=GitService(settings.REPO_PATH),
    file_handler=FileHandler(str(settings.REPO_PATH)),
    planner_config=PlannerConfig(),
    # Heavy services are explicitly None to force lazy loading or registry usage
    cognitive_service=None,
    knowledge_service=KnowledgeService(settings.REPO_PATH),  # Lightweight
    qdrant_service=None,
    auditor_context=None,
)


def _build_context_service() -> ContextService:
    """
    Factory for ContextService, wired at the CLI composition root.
    Uses the registry to ensure singletons are used.
    """
    # NOTE: In a fully async CLI, we would await these.
    # For now, ContextService will fetch them lazily if passed as None.
    return ContextService(
        qdrant_client=None,  # Lazy load via registry inside service if needed
        cognitive_service=None,  # Lazy load via registry
        config={},
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
    )


# Wire the factory into CoreContext
core_context.context_service_factory = _build_context_service


# ID: c1414598-a5f8-46c2-8ff9-3a141bea3b11
def register_all_commands(app_instance: typer.Typer) -> None:
    """Register all command groups and inject context declaratively."""
    app_instance.add_typer(check.check_app, name="check")
    app_instance.add_typer(coverage.coverage_app, name="coverage")
    app_instance.add_typer(enrich.enrich_app, name="enrich")
    app_instance.add_typer(fix_app, name="fix")
    app_instance.add_typer(inspect.inspect_app, name="inspect")
    app_instance.add_typer(manage.manage_app, name="manage")
    app_instance.add_typer(mind.mind_app, name="mind")
    app_instance.add_typer(run.run_app, name="run")
    app_instance.add_typer(search.search_app, name="search")
    app_instance.add_typer(submit.submit_app, name="submit")
    app_instance.add_typer(secrets.app, name="secrets")
    app_instance.add_typer(context_cli.app, name="context")
    app_instance.add_typer(develop_app, name="develop")
    app_instance.add_typer(check_patterns.patterns_group, name="patterns")
    app_instance.add_typer(dev_sync_app, name="dev")
    app_instance.add_typer(
        check_atomic_actions.atomic_actions_group, name="atomic-actions"
    )
    app_instance.add_typer(tools_app, name="tools")

    # Pattern diagnostics
    app_instance.command(name="inspect-patterns")(inspect_patterns)

    modules_with_context = [
        check,
        coverage,
        enrich,
        fix,
        inspect,
        manage,
        run,
        search,
        submit,
        audit,
    ]
    for module in modules_with_context:
        if hasattr(module, "_context"):
            setattr(module, "_context", core_context)


register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 2429907d-f6f1-47a5-a3af-5df18685c545
def main(ctx: typer.Context) -> None:
    """If no command is specified, launch the interactive menu."""
    ctx.obj = core_context
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
