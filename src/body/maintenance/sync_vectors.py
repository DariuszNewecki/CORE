# src/features/self_healing/sync_vectors.py

"""
Atomic vector synchronization between PostgreSQL and Qdrant.

This tool performs a complete bidirectional sync to ensure consistency:
1. Prune orphaned vectors from Qdrant (vectors without DB links)
2. Prune dangling links from PostgreSQL (links to missing vectors)

These operations MUST happen in this order to avoid race conditions.
Running them together atomically prevents partial sync states.

CONSTITUTIONAL FIX: Uses VectorLinkRepository with proper transaction boundaries.
Transaction management at controller level, not service level.
"""

from __future__ import annotations

from collections.abc import Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointIdsList
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# REFACTORED: Removed direct settings import
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.repositories.vector_link_repository import (
    VectorLinkRepository,
)
from shared.logger import getLogger


logger = getLogger(__name__)


async def _fetch_all_qdrant_ids(
    client: AsyncQdrantClient, collection_name: str
) -> set[str]:
    """
    Fetch all point IDs from the configured Qdrant collection.

    Uses scroll with pagination to handle large collections robustly.

    Args:
        client: Qdrant async client.
        collection_name: Name of the Qdrant collection to scroll.
    """
    all_ids: set[str] = set()
    offset: str | None = None
    while True:
        points, offset = await client.scroll(
            collection_name=collection_name,
            limit=10000,
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


async def _fetch_db_vector_ids(session: AsyncSession) -> set[str]:
    """
    Load all valid vector IDs from core.symbol_vector_links.

    Args:
        session: Injected database session

    Returns a set of vector_id values cast to text for normalization.
    """
    result = await session.execute(
        text(
            "SELECT vector_id::text FROM core.symbol_vector_links WHERE vector_id IS NOT NULL"
        )
    )
    return {str(row[0]) for row in result}


async def _fetch_db_links(session: AsyncSession) -> list[tuple[str, str]]:
    """
    Load all (symbol_id, vector_id) pairs from core.symbol_vector_links.

    Args:
        session: Injected database session

    Returns list of tuples for deletion operations.
    """
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


async def _prune_orphaned_vectors(
    client: AsyncQdrantClient,
    qdrant_ids: set[str],
    db_vector_ids: set[str],
    dry_run: bool,
    collection_name: str,
) -> int:
    """
    Find and delete vectors in Qdrant that have no corresponding DB link.

    Returns the count of orphaned vectors found (and deleted if not dry_run).
    """
    orphaned_ids = list(qdrant_ids - db_vector_ids)
    if not orphaned_ids:
        logger.info("No orphaned vectors found in Qdrant.")
        return 0
    logger.info("Found %s orphaned vector(s) in Qdrant.", len(orphaned_ids))
    if dry_run:
        logger.debug("Would delete from Qdrant")
        for point_id in orphaned_ids[:10]:
            logger.debug("  - %s", point_id)
        if len(orphaned_ids) > 10:
            logger.debug("  - ... and %s more.", len(orphaned_ids) - 10)
        return len(orphaned_ids)
    logger.info("Deleting %s orphaned vector(s) from Qdrant...", len(orphaned_ids))
    await client.delete(
        collection_name=collection_name,
        points_selector=PointIdsList(points=orphaned_ids),
    )
    logger.info("Deleted %s orphaned vector(s).", len(orphaned_ids))
    return len(orphaned_ids)


async def _delete_dangling_links(
    dangling_links: Iterable[tuple[str, str]], session: AsyncSession
) -> int:
    """
    Delete dangling links from core.symbol_vector_links.

    CONSTITUTIONAL FIX: Uses Repository, no commit (caller manages transaction).

    Args:
        dangling_links: List of (symbol_id, vector_id) tuples
        session: Database session (caller manages transaction boundary)

    Returns:
        Count of deleted links
    """
    repo = VectorLinkRepository(session)
    count = await repo.delete_dangling_links(list(dangling_links))

    # NO COMMIT - caller manages transaction
    return count


async def _prune_dangling_links(
    db_links: list[tuple[str, str]],
    qdrant_ids: set[str],
    session: AsyncSession,
    dry_run: bool,
) -> int:
    """
    Find and delete DB links pointing to non-existent Qdrant vectors.

    CONSTITUTIONAL: Transaction boundary managed at this controller level.

    Args:
        db_links: List of (symbol_id, vector_id) tuples from database
        qdrant_ids: Set of vector IDs currently in Qdrant
        session: Injected database session
        dry_run: If True, only report what would be deleted

    Returns the count of dangling links found (and deleted if not dry_run).
    """
    dangling_links = [
        (symbol_id, vector_id)
        for symbol_id, vector_id in db_links
        if vector_id not in qdrant_ids
    ]
    if not dangling_links:
        logger.info("No dangling links found in PostgreSQL.")
        return 0
    logger.info("Found %s dangling link(s) in PostgreSQL.", len(dangling_links))
    if dry_run:
        logger.debug("Would delete from PostgreSQL")
        for symbol_id, vector_id in dangling_links[:10]:
            logger.debug("  - symbol_id=%s, vector_id=%s", symbol_id, vector_id)
        if len(dangling_links) > 10:
            logger.debug("  - ... and %s more.", len(dangling_links) - 10)
        return len(dangling_links)

    logger.info("Deleting %s dangling link(s) from PostgreSQL...", len(dangling_links))

    # CONTROLLER MANAGES TRANSACTION BOUNDARY
    deleted_count = await _delete_dangling_links(dangling_links, session)
    await session.commit()  # Transaction boundary at controller level

    logger.info("Deleted %s dangling link(s).", deleted_count)
    return deleted_count


async def _async_sync_vectors(
    session: AsyncSession,
    dry_run: bool,
    qdrant_service: QdrantService | None = None,
    qdrant_url: str | None = None,
    collection_name: str | None = None,
) -> tuple[int, int]:
    """
    Core async logic for complete vector synchronization.

    Args:
        session: Injected database session
        dry_run: If True, only report what would be changed
        qdrant_service: Optional injected Qdrant service
        qdrant_url: Qdrant server URL (required when qdrant_service is None)
        collection_name: Qdrant collection name

    Returns (orphans_pruned, dangling_pruned) counts.
    """
    if collection_name is None:
        raise ValueError("collection_name is required for vector sync")

    logger.info("Starting vector synchronization...")
    if dry_run:
        logger.info("DRY RUN MODE: No changes will be made.")
    logger.info("Phase 0: Loading current state...")
    if qdrant_service is None:
        if qdrant_url is None:
            raise ValueError(
                "qdrant_url is required when qdrant_service is not provided"
            )
        client = AsyncQdrantClient(url=qdrant_url)
    else:
        client = qdrant_service.client
    logger.info("Fetching vector IDs from Qdrant...")
    qdrant_ids = await _fetch_all_qdrant_ids(client, collection_name)
    logger.info("Found %s vectors in Qdrant.", len(qdrant_ids))
    logger.info("Fetching vector links from PostgreSQL...")
    db_vector_ids = await _fetch_db_vector_ids(session)
    db_links = await _fetch_db_links(session)
    logger.info("Found %s valid vector IDs in PostgreSQL.", len(db_vector_ids))
    logger.info("Found %s total symbol-vector links.", len(db_links))
    logger.info("Phase 1: Pruning orphaned vectors from Qdrant...")
    orphans_pruned = await _prune_orphaned_vectors(
        client, qdrant_ids, db_vector_ids, dry_run, collection_name
    )
    logger.info("Phase 2: Pruning dangling links from PostgreSQL...")
    dangling_pruned = await _prune_dangling_links(
        db_links, qdrant_ids, session, dry_run
    )
    logger.info("Synchronization Summary")
    logger.info("  • Orphaned vectors pruned: %s", orphans_pruned)
    logger.info("  • Dangling links pruned: %s", dangling_pruned)
    if orphans_pruned == 0 and dangling_pruned == 0:
        logger.info("Vector store is perfectly synchronized!")
    elif dry_run:
        logger.info("Issues found. Run with --write to fix them.")
    else:
        logger.info("Synchronization complete!")
    return (orphans_pruned, dangling_pruned)


# ID: 2ba0085c-70d8-4a2f-b3f5-a41479fba562
async def main_sync(
    session: AsyncSession,
    write: bool = False,
    dry_run: bool = False,
    qdrant_url: str | None = None,
    collection_name: str | None = None,
) -> None:
    """
    Synchronize vector database between PostgreSQL and Qdrant.

    This performs atomic bidirectional synchronization:
    1. Removes orphaned vectors from Qdrant (no DB link)
    2. Removes dangling links from PostgreSQL (no Qdrant vector)

    Args:
        session: Injected database session
        write: If True, apply changes (default: False)
        dry_run: If True, only report what would change (default: False)
        qdrant_url: Qdrant server URL
        collection_name: Qdrant collection name

    Example:
        poetry run core-admin fix vector-sync --dry-run
        poetry run core-admin fix vector-sync --write
    """
    effective_dry_run = dry_run or not write
    await _async_sync_vectors(
        session,
        dry_run=effective_dry_run,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
    )


# ID: 45b243cb-5331-464d-a50d-13a1310e672a
async def main_async(
    session: AsyncSession,
    write: bool = False,
    dry_run: bool = False,
    qdrant_service: QdrantService | None = None,
    qdrant_url: str | None = None,
    collection_name: str | None = None,
) -> tuple[int, int]:
    """
    Async entry point for orchestrators that own the event loop.
    Accepts optional qdrant_service for JIT injection.

    Args:
        session: Injected database session
        write: If True, apply changes (default: False)
        dry_run: If True, only report what would change (default: False)
        qdrant_service: Optional injected Qdrant service
        qdrant_url: Qdrant server URL (used when qdrant_service is None)
        collection_name: Qdrant collection name

    Returns (orphans_pruned, dangling_pruned) counts.
    """
    effective_dry_run = dry_run or not write
    return await _async_sync_vectors(
        session,
        dry_run=effective_dry_run,
        qdrant_service=qdrant_service,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
    )
