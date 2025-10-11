# src/features/self_healing/prune_orphaned_vectors.py
"""
A self-healing tool to find and delete orphaned vectors from the Qdrant database.
An orphan is a vector whose corresponding symbol no longer exists in the main database.
"""

from __future__ import annotations

import asyncio

import typer
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointIdsList
from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

log = getLogger("prune_orphaned_vectors")
console = Console()


async def _async_prune_orphans(dry_run: bool):
    """The core async logic for finding and pruning orphaned vectors."""
    console.print("[bold cyan]🌿 Starting orphan vector pruning process...[/bold cyan]")

    valid_vector_ids = set()
    try:
        # 1. Get the ground truth: all valid vector IDs from the link table.
        console.print("   -> Fetching valid vector IDs from PostgreSQL link table...")
        async with get_session() as session:
            result = await session.execute(
                text("SELECT vector_id FROM core.symbol_vector_links")
            )
            valid_vector_ids = {row[0] for row in result}
        console.print(
            f"      - Found {len(valid_vector_ids)} valid vector links in the main database."
        )

    except Exception as e:
        console.print(f"[bold red]❌ Database query failed: {e}[/bold red]")
        raise typer.Exit(code=1)

    # 2. Get the current state: all vector IDs from the vector store
    qdrant_service = AsyncQdrantClient(url=settings.QDRANT_URL)
    vector_point_ids = set()
    try:
        console.print("   -> Fetching all vector point IDs from Qdrant...")
        all_points, _ = await qdrant_service.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        vector_point_ids = {str(point.id) for point in all_points}
        console.print(f"      - Found {len(vector_point_ids)} vectors in Qdrant.")

    except Exception as e:
        console.print(
            f"[bold red]❌ Failed to connect to or query Qdrant: {e}[/bold red]"
        )
        raise typer.Exit(code=1)

    # 3. Compare the two sets to find the orphans
    orphaned_ids = list(vector_point_ids - valid_vector_ids)

    if not orphaned_ids:
        console.print(
            "\n[bold green]✅ No orphaned vectors found. The vector store is clean.[/bold green]"
        )
        return

    console.print(
        f"\n[bold yellow]Found {len(orphaned_ids)} orphaned vectors to prune.[/bold yellow]"
    )

    if dry_run:
        console.print(
            "\n[bold yellow]-- DRY RUN: The following vector point IDs would be deleted --[/bold yellow]"
        )
        for point_id in orphaned_ids[:20]:
            console.print(f"  - {point_id}")
        if len(orphaned_ids) > 20:
            console.print(f"  - ... and {len(orphaned_ids) - 20} more.")
        return

    # 4. Execute the deletion
    console.print("\n[bold]Pruning orphaned vectors from Qdrant...[/bold]")
    await qdrant_service.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=PointIdsList(points=orphaned_ids),
    )

    console.print(
        f"[bold green]✅ Successfully pruned {len(orphaned_ids)} orphaned vectors.[/bold green]"
    )


# ID: 47ae55f7-19bb-4bd9-9361-e33733a64ba9
def main_sync(
    write: bool = typer.Option(
        False, "--write", help="Permanently delete orphaned vectors from Qdrant."
    ),
):
    """Entry point for the Typer command."""
    asyncio.run(_async_prune_orphans(dry_run=not write))
