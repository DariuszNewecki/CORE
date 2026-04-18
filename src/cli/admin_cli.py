# src/cli/admin_cli.py
"""
CORE Admin CLI - The Constitutional Command Center.

Enforces Resource-First Architecture (v2.0) as defined in
.intent/rules/cli/interface_design.json.

UNIX Philosophy: CLI provides atomic resource actions; Makefile composes them.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from cli.commands.daemon import daemon_app
from cli.commands.interactive_test import app as interactive_test_app
from cli.commands.refactor import refactor_app
from cli.commands.status import status_app
from cli.interactive import launch_interactive_menu
from cli.logic.tools import tools_app
from cli.resources.admin import app as admin_app
from cli.resources.code import app as code_app
from cli.resources.constitution import app as constitution_app
from cli.resources.context import app as context_app
from cli.resources.database import app as database_app
from cli.resources.dev import app as dev_app
from cli.resources.project import app as project_app
from cli.resources.proposals import app as proposals_app
from cli.resources.runtime import app as runtime_app
from cli.resources.secrets import app as secrets_app
from cli.resources.symbols import app as symbols_app
from cli.resources.vectors import app as vectors_app
from cli.resources.workers import app as workers_app
from shared.infrastructure.database.session_manager import get_session


console = Console()
app = typer.Typer(
    name="core-admin",
    help="CORE: The Self-Improving System Architect's Toolkit.",
    no_args_is_help=False,
)
core_context = create_core_context(service_registry)


# ID: ceac52ff-a86d-47f6-9c1e-2580932a3767
def register_all_commands(app_instance: typer.Typer) -> None:
    """
    Register CLI commands according to the Resource-First hierarchy.
    Legacy Verb-First groups (fix, check, inspect) have been purged.
    """
    app_instance.add_typer(admin_app, name="admin")
    app_instance.add_typer(code_app, name="code")
    app_instance.add_typer(context_app, name="context")
    app_instance.add_typer(database_app, name="database")
    app_instance.add_typer(runtime_app, name="runtime")
    app_instance.add_typer(symbols_app, name="symbols")
    app_instance.add_typer(vectors_app, name="vectors")
    app_instance.add_typer(workers_app, name="workers")
    app_instance.add_typer(constitution_app, name="constitution")
    app_instance.add_typer(proposals_app, name="proposals")
    app_instance.add_typer(project_app, name="project")
    app_instance.add_typer(dev_app, name="dev")
    app_instance.add_typer(interactive_test_app, name="interactive-test")
    app_instance.add_typer(refactor_app, name="refactor")
    app_instance.add_typer(tools_app, name="tools")
    app_instance.add_typer(secrets_app, name="secrets")
    app_instance.add_typer(daemon_app, name="daemon")
    app_instance.add_typer(status_app, name="status")


register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 1f5f3dc8-cbc5-426f-8049-271f45e155f5
def main(ctx: typer.Context) -> None:
    """Bootstrap services and launch TUI if no command given."""
    service_registry.prime(get_session)
    ctx.obj = core_context
    if ctx.invoked_subcommand is None:
        logger.info(
            "[bold green]🛏  CORE Admin Active. Resource-First Architecture v2.0 engaged.[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
