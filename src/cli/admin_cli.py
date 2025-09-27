"""The single, canonical entry point for the core-admin CLI.
This module assembles all command groups into a single Typer application.
"""

from __future__ import annotations

import typer
from rich.console import Console

# --- Command Group Imports ---
from cli.commands import (
    agent,
    build,
    byor,
    capability,
    chat,
    check,
    db,
    fixer,
    guard,
    interactive,
    knowledge,
    knowledge_sync,
    new,
    proposal_service,
    run,
    system,
    tools,
)
from features.governance import key_management_service
from features.project_lifecycle import bootstrap_service

console = Console()

# --- Main Application ---
app = typer.Typer(
    name="core-admin",
    help="""
    CORE: The Self-Improving System Architect's Toolkit.

    This CLI is the primary interface for operating and governing the CORE system.
    Run with no arguments to enter the interactive menu.
    """,
    no_args_is_help=False,  # We want to launch the interactive menu by default
)


# --- Centralized Registration Helper ---
def register_all_commands(app_instance: typer.Typer) -> None:
    """
    Register all command groups in the correct order.

    The order here determines the order in the --help output.
    """
    command_modules = [
        system,
        check,
        fixer,
        db,
        knowledge,
        knowledge_sync,
        run,
        build,
        tools,
        agent,
        proposal_service,
        key_management_service,
        new,
        bootstrap_service,
        byor,
        guard,
        capability,
        chat,
    ]

    for module in command_modules:
        module.register(app_instance)


# --- Command Registration ---
register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 25555fd8-2556-4a77-b222-a68988ef2b01
def main(ctx: typer.Context):
    """
    If no command is specified, launch the interactive menu.
    """
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        interactive.launch_interactive_menu()


if __name__ == "__main__":
    app()
