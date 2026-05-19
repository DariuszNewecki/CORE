# src/cli/resources/database/sync.py
"""
Database synchronization command.

Synchronizes PostgreSQL schema and seeds constitutional data.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("sync")
@command_meta(
    canonical_name="database.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize database with codebase symbols.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: acb50cd7-0423-4837-bcda-e9ab8bc16a46
async def sync_database(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes to database (default: dry-run)"
    ),
) -> None:
    """
    Synchronize database with codebase symbols.

    Scans the codebase and syncs all symbols to the database knowledge graph.

    Constitutional Compliance:
    - Enforces 'knowledge.database_ssot'
    - All changes logged to audit trail
    - Atomic action with rollback capability

    Examples:
        # Dry-run (show what would change)
        core-admin database sync

        # Apply changes
        core-admin database sync --write
    """
    console.print("[bold cyan]📊 Database Synchronization[/bold cyan]")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    console.print()
    try:
        from body.introspection.sync_service import run_sync_with_db

        if not write:
            console.print("[yellow]DRY-RUN: Use --write to persist changes[/yellow]")
            return
        async with get_session() as session:
            result = await run_sync_with_db(session)
            if result.ok:
                stats = result.data
                console.print("[green]✅ Synchronization completed[/green]")
                console.print()
                console.print(f"  Scanned: {stats.get('scanned', 0)} symbols")
                console.print(f"  Inserted: {stats.get('inserted', 0)}")
                console.print(f"  Updated: {stats.get('updated', 0)}")
                console.print(f"  Deleted: {stats.get('deleted', 0)}")
            else:
                console.print(f"[red]❌ Sync failed: {result.error}[/red]")
                raise typer.Exit(1)
    except Exception as e:
        logger.error("Database sync failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)
