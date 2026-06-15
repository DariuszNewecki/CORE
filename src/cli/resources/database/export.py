# src/cli/resources/database/export.py
"""
Database export command.

Exports operational data to its canonical, read-only YAML representation.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from cli.utils import core_command

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("export")
@core_command(dangerous=False, requires_context=True)
# ID: e7f86889-85aa-40c7-92f9-19f751f8162f
async def export_database(ctx: typer.Context) -> None:
    """
    Export database operational data to its canonical YAML representation.

    Each operational domain and the vector metadata are written to their
    fixed, read-only YAML files under the repo (schema-as-truth), via
    FileHandler. The destination paths are canonical and not configurable.

    Constitutional Compliance:
    - Uses FileHandler for traceable mutations

    Examples:
        core-admin database export
    """
    console.print("[bold cyan]📤 Database Export[/bold cyan]")
    console.print()
    try:
        from cli.logic.db import export_data

        await export_data(ctx)
        console.print("[green]✅ Export completed[/green]")
    except Exception as e:
        logger.error("Database export failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)
