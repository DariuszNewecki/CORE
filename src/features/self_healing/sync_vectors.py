# src/features/self_healing/sync_vectors.py
"""
Atomic vector synchronization between PostgreSQL and Qdrant.

This tool performs a complete bidirectional sync to ensure consistency:
1. Prune orphaned vectors from Qdrant (vectors without DB links)
2. Prune dangling links from PostgreSQL (links to missing vectors)

These operations MUST happen in this order to avoid race conditions.
Running them together atomically prevents partial sync states.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import typer
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointIdsList
from rich.console import Console
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

logger = getLogger(__name__)
console = Console()


# ============================================================================
# SHARED UTILITIES
# ============================================================================


async def _fetch_all_qdrant_ids(client: AsyncQdrantClient) -> set[str]:
    """
    Fetch all point IDs from the configured Qdrant collection.

    Uses scroll with pagination to handle large collections robustly.
    """
    all_ids: set[str] = set()
    offset: str | None = None

    while True:
        points, offset = await client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            limit=10_000,
            with_payload=False,
            with_vectors=False,
            offset=offset,
        )
        if not points:
            break

        all_ids.update(str(point.id) for point in points)

        if offset is None:
            break

    return all_ids


async def _fetch_db_vector_ids() -> set[str]:
    """
    Load all valid vector IDs from core.symbol_vector_links.

    Returns a set of vector_id values cast to text for normalization.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT vector_id::text FROM core.symbol_vector_links WHERE vector_id IS NOT NULL"
            )
        )
        return {str(row[0]) for row in result}


async def _fetch_db_links() -> list[tuple[str, str]]:
    """
    Load all (symbol_id, vector_id) pairs from core.symbol_vector_links.

    Returns list of tuples for deletion operations.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT symbol_id::text, vector_id::text
                FROM core.symbol_vector_links
                WHERE vector_id IS NOT NULL
                """
            )
        )
        return [(row[0], row[1]) for row in result]


# ============================================================================
# PHASE 1: PRUNE ORPHANED VECTORS FROM QDRANT
# ============================================================================


async def _prune_orphaned_vectors(
    client: AsyncQdrantClient,
    qdrant_ids: set[str],
    db_vector_ids: set[str],
    dry_run: bool,
) -> int:
    """
    Find and delete vectors in Qdrant that have no corresponding DB link.

    Returns the count of orphaned vectors found (and deleted if not dry_run).
    """
    orphaned_ids = list(qdrant_ids - db_vector_ids)

    if not orphaned_ids:
        logger.info("   [green]✓[/green] No orphaned vectors found in Qdrant.")
        return 0

    logger.info(
        f"   [yellow]⚠[/yellow] Found {len(orphaned_ids)} orphaned vector(s) in Qdrant."
    )

    if dry_run:
        logger.info("      [dim](Would delete from Qdrant)[/dim]")
        for point_id in orphaned_ids[:10]:
            logger.info(f"        - {point_id}")
        if len(orphaned_ids) > 10:
            logger.info(f"        - ... and {len(orphaned_ids) - 10} more.")
        return len(orphaned_ids)

    # Actually delete
    logger.info(f"      Deleting {len(orphaned_ids)} orphaned vector(s) from Qdrant...")
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=PointIdsList(points=orphaned_ids),
    )
    logger.info(
        f"      [green]✓[/green] Deleted {len(orphaned_ids)} orphaned vector(s)."
    )

    return len(orphaned_ids)


# ============================================================================
# PHASE 2: PRUNE DANGLING LINKS FROM POSTGRESQL
# ============================================================================


async def _delete_dangling_links(
    dangling_links: Iterable[tuple[str, str]],
) -> int:
    """
    Delete dangling links from core.symbol_vector_links.

    Expects (symbol_id, vector_id_as_text) tuples.
    """
    count = 0
    async with get_session() as session:
        for symbol_id, vector_id in dangling_links:
            await session.execute(
                text(
                    """
                    DELETE FROM core.symbol_vector_links
                    WHERE symbol_id = :symbol_id
                      AND vector_id = :vector_id::uuid
                    """
                ),
                {"symbol_id": symbol_id, "vector_id": vector_id},
            )
            count += 1

        await session.commit()

    return count


async def _prune_dangling_links(
    db_links: list[tuple[str, str]],
    qdrant_ids: set[str],
    dry_run: bool,
) -> int:
    """
    Find and delete DB links pointing to non-existent Qdrant vectors.

    Returns the count of dangling links found (and deleted if not dry_run).
    """
    dangling_links = [
        (symbol_id, vector_id)
        for symbol_id, vector_id in db_links
        if vector_id not in qdrant_ids
    ]

    if not dangling_links:
        logger.info("   [green]✓[/green] No dangling links found in PostgreSQL.")
        return 0

    logger.info(
        f"   [yellow]⚠[/yellow] Found {len(dangling_links)} dangling link(s) in PostgreSQL."
    )

    if dry_run:
        logger.info("      [dim](Would delete from PostgreSQL)[/dim]")
        for symbol_id, vector_id in dangling_links[:10]:
            logger.info(f"        - symbol_id={symbol_id}, vector_id={vector_id}")
        if len(dangling_links) > 10:
            logger.info(f"        - ... and {len(dangling_links) - 10} more.")
        return len(dangling_links)

    # Actually delete
    logger.info(
        f"      Deleting {len(dangling_links)} dangling link(s) from PostgreSQL..."
    )
    deleted_count = await _delete_dangling_links(dangling_links)
    logger.info(f"      [green]✓[/green] Deleted {deleted_count} dangling link(s).")

    return deleted_count


# ============================================================================
# MAIN SYNC LOGIC
# ============================================================================


async def _async_sync_vectors(
    dry_run: bool, qdrant_service: QdrantService | None = None
) -> tuple[int, int]:
    """
    Core async logic for complete vector synchronization.

    Returns (orphans_pruned, dangling_pruned) counts.
    """
    logger.info("[bold cyan]🔄 Starting vector synchronization...[/bold cyan]")

    if dry_run:
        logger.info("   [yellow]DRY RUN MODE: No changes will be made.[/yellow]\n")

    # Step 0: Load all data
    logger.info("[bold]Phase 0: Loading current state...[/bold]")

    # Use injected service or create new one if missing
    if qdrant_service is None:
        client = AsyncQdrantClient(url=settings.QDRANT_URL)
    else:
        client = qdrant_service.client

    logger.info("   → Fetching vector IDs from Qdrant...")
    qdrant_ids = await _fetch_all_qdrant_ids(client)
    logger.info(f"      Found {len(qdrant_ids)} vectors in Qdrant.")

    logger.info("   → Fetching vector links from PostgreSQL...")
    db_vector_ids = await _fetch_db_vector_ids()
    db_links = await _fetch_db_links()
    logger.info(f"      Found {len(db_vector_ids)} valid vector IDs in PostgreSQL.")
    logger.info(f"      Found {len(db_links)} total symbol-vector links.\n")

    # Step 1: Prune orphaned vectors from Qdrant
    logger.info("[bold]Phase 1: Pruning orphaned vectors from Qdrant...[/bold]")
    orphans_pruned = await _prune_orphaned_vectors(
        client, qdrant_ids, db_vector_ids, dry_run
    )

    # Step 2: Prune dangling links from PostgreSQL
    logger.info("\n[bold]Phase 2: Pruning dangling links from PostgreSQL...[/bold]")
    dangling_pruned = await _prune_dangling_links(db_links, qdrant_ids, dry_run)

    # Summary
    logger.info("\n[bold cyan]📊 Synchronization Summary[/bold cyan]")
    logger.info(f"   • Orphaned vectors pruned: {orphans_pruned}")
    logger.info(f"   • Dangling links pruned: {dangling_pruned}")

    if orphans_pruned == 0 and dangling_pruned == 0:
        logger.info(
            "\n[bold green]✅ Vector store is perfectly synchronized![/bold green]"
        )
    elif dry_run:
        logger.info(
            "\n[bold yellow]⚠ Issues found. Run with --write to fix them.[/bold yellow]"
        )
    else:
        logger.info("\n[bold green]✅ Synchronization complete![/bold green]")

    return (orphans_pruned, dangling_pruned)


# ============================================================================
# PUBLIC ENTRY POINTS
# ============================================================================


# ID: 8f4a3c21-9b7e-4d2f-a8c3-5e1f9a2b3c4d
def main_sync(
    write: bool = typer.Option(
        False,
        "--write",
        help="Permanently fix synchronization issues. Without this, runs in dry-run mode.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be changed without making changes.",
    ),
) -> None:
    """
    Synchronize vector database between PostgreSQL and Qdrant.

    This performs atomic bidirectional synchronization:
    1. Removes orphaned vectors from Qdrant (no DB link)
    2. Removes dangling links from PostgreSQL (no Qdrant vector)

    Example:
        poetry run core-admin fix vector-sync --dry-run
        poetry run core-admin fix vector-sync --write
    """
    effective_dry_run = dry_run or not write
    asyncio.run(_async_sync_vectors(dry_run=effective_dry_run))


# ID: 2c5d8f91-4a7b-3e6c-9d1f-8b2a4c7e5f3d
async def main_async(
    write: bool = False,
    dry_run: bool = False,
    qdrant_service: QdrantService | None = None,
) -> tuple[int, int]:
    """
    Async entry point for orchestrators that own the event loop.
    Accepts optional qdrant_service for JIT injection.

    Returns (orphans_pruned, dangling_pruned) counts.
    """
    effective_dry_run = dry_run or not write
    return await _async_sync_vectors(
        dry_run=effective_dry_run, qdrant_service=qdrant_service
    )
