# src/body/cli/admin_cli.py
# ID: body.cli.admin_cli

"""
CORE Admin CLI - The Constitutional Command Center.

Enforces Resource-First Architecture (v2.0) as defined in
.intent/rules/cli/interface_design.json.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.commands.check import check_app
from body.cli.commands.fix import fix_app

# 2. Remaining Category-Based Apps (Non-Purged)
from body.cli.commands.inspect import inspect_app
from body.cli.commands.status import status_app
from body.cli.commands.submit import submit_app
from body.cli.interactive import launch_interactive_menu
from body.cli.resources.code import app as code_app
from body.cli.resources.constitution import app as constitution_app

# 1. Resource-First Imports (The New Brain)
from body.cli.resources.database import app as database_app
from body.cli.resources.dev import app as dev_app
from body.cli.resources.project import app as project_app
from body.cli.resources.proposals import app as proposals_app
from body.cli.resources.symbols import app as symbols_app
from body.cli.resources.vectors import app as vectors_app

# 3. Infrastructure
from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session


console = Console()

app = typer.Typer(
    name="core-admin",
    help="CORE: The Self-Improving System Architect's Toolkit.",
    no_args_is_help=False,
)

# Bootstrap the context (wiring all services)
core_context = create_core_context(service_registry)


# ID: 5519f6ee-d27e-4116-94b4-d981ede63650
def register_all_commands(app_instance: typer.Typer) -> None:
    """Register CLI commands according to the Resource-First hierarchy."""

    # --- TIER 1: RESOURCE-FIRST (The Standard Interface) ---
    app_instance.add_typer(code_app, name="code")  # Logic, tests, audit
    app_instance.add_typer(database_app, name="database")  # Postgres state
    app_instance.add_typer(symbols_app, name="symbols")  # Knowledge graph identity
    app_instance.add_typer(vectors_app, name="vectors")  # Semantic memory
    app_instance.add_typer(constitution_app, name="constitution")  # The Law (.intent)
    app_instance.add_typer(proposals_app, name="proposals")  # A3 Change management
    app_instance.add_typer(project_app, name="project")  # Scaffolding & Onboarding
    app_instance.add_typer(dev_app, name="dev")  # Human/AI workflows

    # --- TIER 2: INSPECTION & UTILITIES ---
    app_instance.add_typer(inspect_app, name="inspect")  # Deep forensics
    app_instance.add_typer(fix_app, name="fix")  # Self-healing & remediation (A2)
    app_instance.add_typer(submit_app, name="submit")  # Final integration

    # --- TIER 3: LEGACY BACKWARD COMPATIBILITY ---
    # manage_app is removed here because the directory was deleted
    app_instance.add_typer(fix_app, name="legacy-fix", hidden=True)
    app_instance.add_typer(check_app, name="legacy-check", hidden=True)
    app_instance.add_typer(status_app, name="legacy-status", hidden=True)


# Register everything
register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 7bab4a62-0125-464c-a1d7-633b8942d8c8
def main(ctx: typer.Context) -> None:
    """Bootstrap services and launch TUI if no command given."""
    service_registry.prime(get_session)
    ctx.obj = core_context

    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]🏛️  CORE Admin Active. Resource-First Architecture v2.0 engaged.[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
