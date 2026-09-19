# src/cli/resources/database/status.py
"""
Database status command.

Shows health metrics, connection status, and diagnostics.

Read-only (ADR-162 D2/D3): never creates the ledger or any other object.
Reports pending migrations, ledger/schema contradictions (recorded entries
whose verify probe fails) and, when the ledger is empty on a populated
schema, the declared baseline that matches — a suggestion for
``database migrate --adopt-baseline``, never an action.

Exit codes (scriptable): 0 current; 2 pending, contradictory or unledgered;
1 the check itself failed.
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
            "ledger_present": report.ledger_present,
            "schema_present": report.schema_present,
            "applied_migrations": sorted(report.applied_migrations),
            "pending_migrations": report.pending_migrations,
            "probe_failures": report.probe_failures,
            "baseline_suggestion": report.baseline_suggestion,
            "current": report.is_current,
        }
        sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    else:
        console.print("[bold cyan]📊 Database Status[/bold cyan]")
        console.print()
        _display_status_table(report, detailed)
    if not report.is_current:
        raise typer.Exit(2)


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
    mig_table.add_row("Ledger", "present" if report.ledger_present else "absent")
    mig_table.add_row("Applied", str(len(report.applied_migrations)))
    mig_table.add_row("Pending", str(len(report.pending_migrations)))
    mig_table.add_row("Probe failures", str(len(report.probe_failures)))
    console.print(mig_table)
    if report.probe_failures:
        console.print()
        console.print(
            "[red]✗ Ledger/schema contradiction — recorded but the probe fails:[/red]"
        )
        for mig in report.probe_failures:
            console.print(f"  • {mig}")
    if report.schema_present and not report.applied_migrations:
        console.print()
        if report.baseline_suggestion:
            console.print(
                "[yellow]⚠️  Empty ledger on a populated schema.[/yellow] Matches "
                f"baseline [bold]{report.baseline_suggestion}[/bold]; adopt it with:\n"
                f"  core-admin database migrate --adopt-baseline "
                f"{report.baseline_suggestion} --write"
            )
        else:
            console.print(
                "[yellow]⚠️  Empty ledger on a populated schema[/yellow] and no "
                "declared baseline matches it."
            )
    if report.pending_migrations:
        console.print()
        console.print("[yellow]⚠️  Pending migrations:[/yellow]")
        for mig in report.pending_migrations:
            console.print(f"  • {mig}")
