# src/body/cli/admin_cli.py

"""
The single, canonical entry point for the core-admin CLI.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.commands import (
    check_atomic_actions,
    check_patterns,
    coverage,
    enrich,
    governance,
    inspect,
    interactive_test,
    mind,
    run,
    search,
    secrets,
    submit,
)
from body.cli.commands.autonomy import autonomy_app
from body.cli.commands.check import check_app
from body.cli.commands.dev_sync import dev_sync_app
from body.cli.commands.develop import develop_app
from body.cli.commands.diagnostics import app as diagnostics_app
from body.cli.commands.fix import fix_app
from body.cli.commands.inspect_patterns import inspect_patterns
from body.cli.commands.manage import manage
from body.cli.interactive import launch_interactive_menu
from body.cli.logic.tools import tools_app
from body.services.service_registry import service_registry
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
    ),
    no_args_is_help=False,
)

core_context = CoreContext(
    registry=service_registry,
    git_service=GitService(settings.REPO_PATH),
    file_handler=FileHandler(str(settings.REPO_PATH)),
    planner_config=PlannerConfig(),
    cognitive_service=None,
    knowledge_service=KnowledgeService(settings.REPO_PATH),
    qdrant_service=None,
    auditor_context=None,
)


def _build_context_service() -> ContextService:
    """Factory for ContextService."""
    return ContextService(
        qdrant_client=None,
        cognitive_service=None,
        config={},
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
        service_registry=service_registry,
    )


core_context.context_service_factory = _build_context_service


# ID: c1414598-a5f8-46c2-8ff9-3a141bea3b11
def register_all_commands(app_instance: typer.Typer) -> None:
    """Register all command groups."""
    app_instance.add_typer(check_app, name="check")
    app_instance.add_typer(coverage.coverage_app, name="coverage")
    app_instance.add_typer(enrich.enrich_app, name="enrich")
    app_instance.add_typer(fix_app, name="fix")
    app_instance.add_typer(governance.governance_app, name="governance")
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
    app_instance.add_typer(autonomy_app, name="autonomy")
    app_instance.add_typer(tools_app, name="tools")
    app_instance.add_typer(diagnostics_app, name="diagnostics")
    app_instance.add_typer(interactive_test.app, name="interactive-test")
    app_instance.command(name="inspect-patterns")(inspect_patterns)


register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 2429907d-f6f1-47a5-a3af-5df18685c545
def main(ctx: typer.Context) -> None:
    """If no command is specified, launch the interactive menu."""

    # CONSTITUTIONAL FIX: Prime the ServiceRegistry here.
    # This ensures every CLI command has access to a governed session factory.
    service_registry.prime(get_session)

    ctx.obj = core_context
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
