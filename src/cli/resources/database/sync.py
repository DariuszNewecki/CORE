# src/cli/resources/database/sync.py
"""
Database synchronization command.

Synchronizes PostgreSQL schema and seeds constitutional data.
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
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
    logger.info("[bold cyan]📊 Database Synchronization[/bold cyan]")
    logger.info("Mode: %s", "WRITE" if write else "DRY-RUN")
    console.print()
    try:
        from body.introspection.sync_service import run_sync_with_db

        if not write:
            logger.info("[yellow]DRY-RUN: Use --write to persist changes[/yellow]")
            return
        async with get_session() as session:
            result = await run_sync_with_db(session)
            if result.ok:
                stats = result.data
                logger.info("[green]✅ Synchronization completed[/green]")
                logger.info()
                logger.info("  Scanned: %s symbols", stats.get("scanned", 0))
                logger.info("  Inserted: %s", stats.get("inserted", 0))
                logger.info("  Updated: %s", stats.get("updated", 0))
                logger.info("  Deleted: %s", stats.get("deleted", 0))
            else:
                logger.info("[red]❌ Sync failed: %s[/red]", result.error)
                raise typer.Exit(1)
    except Exception as e:
        logger.error("Database sync failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
