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
    coverage,
    enrich,
    fix,
    inspect,
    manage,
    mind,
    run,
    search,
    secrets,
    submit,
)
from body.cli.commands.develop import develop_app
from body.cli.commands.fix import fix_app
from body.cli.interactive import launch_interactive_menu
from body.cli.logic import audit

# New Architecture: Registry
from body.services.service_registry import service_registry
from mind.governance.audit_context import AuditorContext
from services.context import cli as context_cli
from services.context.service import ContextService
from services.database.session_manager import get_session
from services.git_service import GitService
from services.knowledge.knowledge_service import KnowledgeService
from services.storage.file_handler import FileHandler
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlannerConfig
from will.orchestration.cognitive_service import CognitiveService

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
# Note: qdrant_service is deliberately None here to avoid slow startup.
# Services requiring it will fetch it via registry.get_qdrant_service().
core_context = CoreContext(
    registry=service_registry,  # <-- The source of truth
    git_service=GitService(settings.REPO_PATH),
    cognitive_service=CognitiveService(settings.REPO_PATH, qdrant_service=None),
    knowledge_service=KnowledgeService(settings.REPO_PATH),
    qdrant_service=None,
    auditor_context=AuditorContext(settings.REPO_PATH),
    file_handler=FileHandler(str(settings.REPO_PATH)),
    planner_config=PlannerConfig(),
)


def _build_context_service() -> ContextService:
    """
    Factory for ContextService, wired at the CLI composition root.
    Uses the registry to ensure singletons are used.
    """
    return ContextService(
        qdrant_client=core_context.qdrant_service,  # Pass None initially, let Service fetch if needed
        cognitive_service=core_context.cognitive_service,
        config={},
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
    )


# Wire the factory into CoreContext so that lower layers don't need to know
# about services or database wiring.
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
