# src/body/cli/resources/database/export.py
# ID: fd5b5529-caa8-4411-a40a-1f04bead977c
"""
Database export command.

Exports database contents to JSON or SQL format.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("export")
@core_command(dangerous=False, requires_context=True)
# ID: 9d3e5f2a-7c1b-4e8d-9a6f-2b4e8d7c3a1f
async def export_database(
    ctx: typer.Context,
    output_dir: str = typer.Option(
        "backups",
        "--output-dir",
        "-o",
        help="Output directory for export files",
    ),
) -> None:
    """
    Export database operational data to files.

    Exports database tables to canonical YAML representations
    in the specified output directory.

    Constitutional Compliance:
    - Writes to var/ directory (runtime artifacts)
    - Uses FileHandler for traceable mutations

    Examples:
        # Export to default backups directory
        core-admin database export

        # Export to custom directory
        core-admin database export --output-dir exports/2024
    """
    console.print("[bold cyan]📤 Database Export[/bold cyan]")
    console.print(f"Output directory: {output_dir}")
    console.print()

    try:
        from body.cli.logic.db import export_data

        # Use existing export_data function
        export_data(output_dir)

        console.print(f"[green]✅ Export completed to {output_dir}[/green]")

    except Exception as e:
        logger.error("Database export failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
