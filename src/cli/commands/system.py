# src/cli/commands/system.py
from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from features.project_lifecycle.integration_service import integrate_changes

console = Console()
system_app = typer.Typer(
    help="High-level commands for managing the CORE system lifecycle."
)


@system_app.command("integrate", help="Integrates staged code changes into the system.")
# ID: 46b79a8e-3360-4fac-af15-9a52cf0d9a7a
def integrate_command(
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    )
):
    """Orchestrates the full, autonomous integration of staged code changes."""
    asyncio.run(integrate_changes(commit_message))


# ID: e3b37bfa-b8d3-4fd1-83ed-a1b8d063f41d
def register(app: typer.Typer):
    """Register the 'system' command group with the main CLI app."""
    app.add_typer(system_app, name="system")
