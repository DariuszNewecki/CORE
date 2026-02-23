# src/body/cli/resources/database/sync.py
# ID: 0ed02faf-9db8-4a9a-8103-d52dc677245c
"""
Database synchronization command.

Synchronizes PostgreSQL schema and seeds constitutional data.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("sync")
@core_command(dangerous=True, requires_context=True)
# ID: 8f4e2a9c-1d3b-4f7e-9a2c-5e6b8d9f1a3c
async def sync_database(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes to database (default: dry-run)",
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
        from features.introspection.sync_service import run_sync_with_db

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
                console.print(f"[red]❌ Sync failed: {result.error}[/red]", err=True)
                raise typer.Exit(1)

    except Exception as e:
        logger.error("Database sync failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
