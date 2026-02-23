# src/body/cli/resources/database/status.py
# ID: 5c5a89a5-c91d-4c78-a48b-12fbeeb930e0
"""
Database status command.

Shows health metrics, connection status, and diagnostics.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=False)
# ID: 7e2f9d3a-5c1b-4e8d-9a6f-3b4e7d8c2a1f
async def database_status(
    ctx: typer.Context,
    detailed: bool = typer.Option(
        False,
        "--detailed",
        "-d",
        help="Show detailed table statistics",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table or json",
    ),
) -> None:
    """
    Show database health metrics and diagnostics.

    Displays:
    - Connection status
    - Database version
    - Migration status

    Examples:
        # Basic status
        core-admin database status

        # JSON output for scripting
        core-admin database status --format json
    """
    console.print("[bold cyan]📊 Database Status[/bold cyan]")
    console.print()

    try:
        from shared.infrastructure.repositories.db.status_service import (
            status as db_status,
        )

        report = await db_status()

        # JSON output
        if format == "json":
            import json

            result = {
                "connected": report.is_connected,
                "version": report.db_version,
                "applied_migrations": list(report.applied_migrations),
                "pending_migrations": report.pending_migrations,
            }
            print(json.dumps(result, indent=2, default=str))
            return

        # Rich table output
        _display_status_table(report, detailed)

    except Exception as e:
        logger.error("Database status check failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)


# ID: 3a9f5e2d-7c1b-4e8d-9a6f-2b4e8d7c3a1f
def _display_status_table(report, detailed: bool) -> None:
    """Display status information as rich tables."""

    # Connection info
    console.print("[bold]Connection[/bold]")
    conn_table = Table(show_header=False)
    conn_table.add_column("Metric", style="cyan")
    conn_table.add_column("Value")

    conn_table.add_row(
        "Status", "🟢 Connected" if report.is_connected else "🔴 Disconnected"
    )
    conn_table.add_row("Version", report.db_version or "N/A")

    console.print(conn_table)
    console.print()

    # Migration status
    console.print("[bold]Migrations[/bold]")
    mig_table = Table(show_header=False)
    mig_table.add_column("Metric", style="cyan")
    mig_table.add_column("Value")

    mig_table.add_row("Applied", str(len(report.applied_migrations)))
    mig_table.add_row("Pending", str(len(report.pending_migrations)))

    console.print(mig_table)

    if report.pending_migrations:
        console.print()
        console.print("[yellow]⚠️  Pending migrations:[/yellow]")
        for mig in sorted(report.pending_migrations):
            console.print(f"  • {mig}")
