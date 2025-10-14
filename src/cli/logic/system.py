# src/cli/logic/system.py
from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from core.crate_processing_service import process_crates
from features.project_lifecycle.integration_service import integrate_changes
from shared.context import CoreContext

console = Console()

# Global variable to store context, set by the registration layer.
_context: CoreContext | None = None


# ID: 46b79a8e-3360-4fac-af15-9a52cf0d9a7a
def integrate_command(
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
):
    """Orchestrates the full, autonomous integration of staged code changes."""
    if _context is None:
        console.print(
            "[bold red]Error: Context not initialized for integrate[/bold red]"
        )
        raise typer.Exit(code=1)

    # Pass the context to the underlying service
    asyncio.run(integrate_changes(context=_context, commit_message=commit_message))


# ID: 1f2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e
def process_crates_command():
    """Finds, validates, and applies all pending autonomous change proposals."""
    asyncio.run(process_crates())
