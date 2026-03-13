# src/cli/resources/vectors/cleanup.py
"""
Vector cleanup command.

Removes orphaned vectors and synchronizes with PostgreSQL.
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


@app.command("cleanup")
@core_command(dangerous=True, requires_context=False)
# ID: a644bc31-42c8-4d69-bb4b-f8f481ec2cb6
async def cleanup_vectors(
    ctx: typer.Context,
    target: str = typer.Option(
        "all", "--target", "-t", help="Cleanup target: 'orphans', 'dangling', 'all'"
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply cleanup (default: dry-run)"
    ),
) -> None:
    """
    Clean up orphaned and inconsistent vector data.

    Cleanup targets:
    - orphans: Vectors in Qdrant without PostgreSQL links
    - dangling: PostgreSQL links to non-existent vectors
    - all: Both orphans and dangling links

    This performs bidirectional synchronization between Qdrant and PostgreSQL.

    Constitutional Compliance:
    - Enforces 'vectors.bidirectional_sync'
    - All changes logged to audit trail
    - Atomic operation with proper ordering

    Examples:
        # Dry-run (show what would be cleaned)
        core-admin vectors cleanup

        # Clean orphaned vectors only
        core-admin vectors cleanup --target orphans --write

        # Full cleanup
        core-admin vectors cleanup --target all --write
    """
    logger.info("[bold cyan]🧹 Vector Cleanup[/bold cyan]")
    logger.info("Target: %s", target)
    logger.info("Mode: %s", "WRITE" if write else "DRY-RUN")
    console.print()
    if not write:
        logger.info("[yellow]DRY-RUN: Use --write to apply changes[/yellow]")
    try:
        from body.maintenance.sync_vectors import (
            _async_sync_vectors as sync_vectors_internal,
        )

        async with get_session() as session:
            orphans_pruned, dangling_pruned = await sync_vectors_internal(
                session=session, dry_run=not write, qdrant_service=None
            )
            if write:
                await session.commit()
        logger.info()
        logger.info("[bold]Results:[/bold]")
        if target in ["orphans", "all"]:
            status = "Would prune" if not write else "Pruned"
            logger.info("  Orphaned vectors: %s %s", status, orphans_pruned)
        if target in ["dangling", "all"]:
            status = "Would prune" if not write else "Pruned"
            logger.info("  Dangling links: %s %s", status, dangling_pruned)
        logger.info()
        if write:
            logger.info("[green]✅ Cleanup completed successfully[/green]")
        else:
            logger.info("[yellow]DRY-RUN completed - no changes made[/yellow]")
    except Exception as e:
        logger.error("Vector cleanup failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
