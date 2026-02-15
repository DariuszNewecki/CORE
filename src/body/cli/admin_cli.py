# src/body/cli/admin_cli.py
# ID: b05ac309-b737-4171-8b03-42b3ea403ffa

"""
CORE Admin CLI - The Constitutional Command Center.

Enforces Resource-First Architecture (v2.0) as defined in
.intent/rules/cli/interface_design.json.

UNIX Philosophy: CLI provides atomic resource actions; Makefile composes them.
"""

from __future__ import annotations

import typer
from rich.console import Console

# NEW: Import the Interactive Test tool
from body.cli.commands.interactive_test import app as interactive_test_app
from body.cli.commands.refactor import refactor_app

# 2. Interactive UI
from body.cli.interactive import launch_interactive_menu

# 1. Resource-First Imports (The "Neurons")
from body.cli.resources.admin import app as admin_app
from body.cli.resources.code import app as code_app
from body.cli.resources.constitution import app as constitution_app
from body.cli.resources.context import app as context_app
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
    """
    Register CLI commands according to the Resource-First hierarchy.
    Legacy Verb-First groups (fix, check, inspect) have been purged.
    """

    # --- RESOURCE-FIRST INTERFACE ---
    app_instance.add_typer(admin_app, name="admin")  # Forensics & Analytics
    app_instance.add_typer(code_app, name="code")  # Logic, formatting, & quality
    app_instance.add_typer(context_app, name="context")  # Context building for LLMs
    app_instance.add_typer(database_app, name="database")  # Postgres state & migrations
    app_instance.add_typer(symbols_app, name="symbols")  # Identity registry & UUIDs
    app_instance.add_typer(vectors_app, name="vectors")  # Semantic memory & Qdrant
    app_instance.add_typer(
        constitution_app, name="constitution"
    )  # Governance & Policies
    app_instance.add_typer(proposals_app, name="proposals")  # A3 Change management
    app_instance.add_typer(project_app, name="project")  # Lifecycle & Documentation
    app_instance.add_typer(dev_app, name="dev")  # Developer workbench

    # REGISTER NEW INTERACTIVE TOOL
    app_instance.add_typer(interactive_test_app, name="interactive-test")
    app_instance.add_typer(refactor_app, name="refactor")


# Register the resource tree
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
