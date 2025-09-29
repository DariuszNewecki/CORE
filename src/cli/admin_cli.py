# src/cli/admin_cli.py
"""
The single, canonical entry point for the core-admin CLI.
This module assembles all command groups into a single Typer application.
"""
from __future__ import annotations

import typer
from rich.console import Console

# Final, clean imports from the new canonical command structure
from cli.commands import (
    check,
    fix,
    inspect,
    manage,
    run,
    search,
    submit,
)
from cli.interactive import launch_interactive_menu
from shared.logger import getLogger

console = Console()
log = getLogger("admin_cli")

# --- Main Application ---
app = typer.Typer(
    name="core-admin",
    help="""
    CORE: The Self-Improving System Architect's Toolkit.
    This CLI is the primary interface for operating and governing the CORE system.
    """,
    no_args_is_help=False,
)


# --- Centralized Registration Helper ---
# ID: 1a9e8b4c-3d5f-4e6a-8b7c-0d1e2f3a4b5c
def register_all_commands(app_instance: typer.Typer) -> None:
    """Register all command groups in the correct order."""
    modules = [check, fix, inspect, manage, run, search, submit]
    for module in modules:
        module.register(app_instance)


# --- Command Registration ---
register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 2b8c9d0e-1f2a-3b4c-5d6e-7f8a9b0c1d2e
def main(ctx: typer.Context):
    """If no command is specified, launch the interactive menu."""
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
