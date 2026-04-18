# src/cli/resources/database/export.py
"""
Database export command.

Exports database contents to JSON or SQL format.
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("export")
@core_command(dangerous=False, requires_context=True)
# ID: e7f86889-85aa-40c7-92f9-19f751f8162f
async def export_database(
    ctx: typer.Context,
    output_dir: str = typer.Option(
        "backups", "--output-dir", "-o", help="Output directory for export files"
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
    logger.info("[bold cyan]📤 Database Export[/bold cyan]")
    logger.info("Output directory: %s", output_dir)
    console.print()
    try:
        from cli.logic.db import export_data

        export_data(output_dir)
        logger.info("[green]✅ Export completed to %s[/green]", output_dir)
    except Exception as e:
        logger.error("Database export failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
