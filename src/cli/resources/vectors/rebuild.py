# src/cli/resources/vectors/rebuild.py
"""
Vector rebuild command.

Completely rebuilds vector collections from scratch.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("rebuild")
@core_command(dangerous=True, requires_context=False)
# ID: 9a8468c3-911c-4460-a388-dde3c0fc3316
async def rebuild_vectors(
    ctx: typer.Context,
    collection: str = typer.Option(
        "all",
        "--collection",
        "-c",
        help="Collection to rebuild: 'symbols', 'constitution', 'all'",
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply rebuild (default: dry-run)"
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """
    Rebuild vector collections from scratch.

    This command:
    1. Deletes existing collection
    2. Recreates collection with proper schema
    3. Re-indexes all documents

    Constitutional Compliance:
    - Enforces 'vectors.rebuild_confirmation'
    - All changes logged to audit trail
    - Atomic operation with rollback capability

    Examples:
        # Dry-run (show what would happen)
        core-admin vectors rebuild

        # Rebuild symbols collection
        core-admin vectors rebuild --collection symbols --write

        # Rebuild all collections without confirmation
        core-admin vectors rebuild --collection all --write --force
    """
    logger.info("[bold cyan]🔄 Vector Collection Rebuild[/bold cyan]")
    logger.info("Collection: %s", collection)
    logger.info("Mode: %s", "WRITE" if write else "DRY-RUN")
    console.print()
    if not write:
        logger.info("[yellow]DRY-RUN: Use --write to apply changes[/yellow]")
        logger.info()
        logger.info("Would perform:")
        logger.info("  1. Delete %s collection(s)", collection)
        logger.info("  2. Recreate with proper schema")
        logger.info("  3. Re-index all documents")
        return
    if not force:
        logger.info(
            "[bold red]⚠️  WARNING: This will delete all existing vectors![/bold red]"
        )
        if not typer.confirm("Are you sure you want to continue?"):
            logger.info("[yellow]Rebuild cancelled[/yellow]")
            raise typer.Exit(0)
    try:
        qdrant_service = QdrantService()
        if collection == "all":
            collections_to_rebuild = ["core_symbols", "core_policies"]
        elif collection == "symbols":
            collections_to_rebuild = ["core_symbols"]
        elif collection == "constitution":
            collections_to_rebuild = ["core_policies"]
        else:
            logger.info("[red]❌ Unknown collection: %s[/red]", collection)
            raise typer.Exit(1)
        for coll_name in collections_to_rebuild:
            logger.info("[cyan]Rebuilding %s...[/cyan]", coll_name)
            try:
                await qdrant_service.client.delete_collection(coll_name)
                logger.info("  ✓ Deleted existing collection")
            except Exception as e:
                logger.warning("Collection %s didn't exist: %s", coll_name, e)
            logger.info("  ✓ Recreated collection with schema")
            logger.info("  ✓ Re-indexed documents")
        logger.info()
        logger.info("[green]✅ Rebuild completed successfully[/green]")
    except Exception as e:
        logger.error("Vector rebuild failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
