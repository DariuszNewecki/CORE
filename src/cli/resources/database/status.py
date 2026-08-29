# src/cli/resources/database/status.py
"""
Database status command.

Shows health metrics, connection status, and diagnostics.
"""

from __future__ import annotations

import json
import logging
import sys

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=False)
# ID: 7c22539d-3f8e-4d18-8457-9d194062a94e
async def database_status(
    ctx: typer.Context,
    detailed: bool = typer.Option(
        False, "--detailed", "-d", help="Show detailed table statistics"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
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
    try:
        from shared.infrastructure.repositories.db.status_service import (
            status as db_status,
        )

        report = await db_status()
    except Exception as e:
        logger.error("Database status check failed", exc_info=True)
        if format == "json":
            # Raw stdout write, not console.print: Rich's markup parser strips
            # bracket-like content and line-wraps long values, either of which
            # can silently corrupt or invalidate a JSON payload (#841).
            sys.stdout.write(
                json.dumps({"connected": False, "error": str(e)}, indent=2) + "\n"
            )
        else:
            console.print("[bold cyan]📊 Database Status[/bold cyan]")
            console.print()
            console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)

    if format == "json":
        result = {
            "connected": report.is_connected,
            "version": report.db_version,
            "applied_migrations": list(report.applied_migrations),
            "pending_migrations": report.pending_migrations,
        }
        sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
        return

    console.print("[bold cyan]📊 Database Status[/bold cyan]")
    console.print()
    _display_status_table(report, detailed)


def _display_status_table(report, detailed: bool) -> None:
    """Display status information as rich tables."""
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
