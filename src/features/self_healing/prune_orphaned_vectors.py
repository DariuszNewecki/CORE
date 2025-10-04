# src/features/self_healing/prune_orphaned_vectors.py
"""
A self-healing tool to find and delete orphaned vectors from the Qdrant database.
An orphan is a vector whose corresponding symbol no longer exists in the
knowledge graph.
"""

from __future__ import annotations

import asyncio

import typer
from core.knowledge_service import KnowledgeService
from qdrant_client import AsyncQdrantClient

# --- START OF AMENDMENT: Import the correct model ---
from qdrant_client.http.models import PointIdsList

# --- END OF AMENDMENT ---
from rich.console import Console
from shared.config import settings
from shared.logger import getLogger

log = getLogger("prune_orphaned_vectors")
console = Console()
REPO_ROOT = settings.REPO_PATH


async def _async_main_sync(dry_run: bool):
    """Main async orchestration for pruning orphaned vectors."""
    log.info("🌿 Starting orphan vector pruning process...")

    knowledge_service = KnowledgeService(REPO_ROOT)
    graph = await knowledge_service.get_graph()
    known_symbol_keys = set(graph.get("symbols", {}).keys())
    log.info(
        f"   -> Found {len(known_symbol_keys)} known symbols in the knowledge graph."
    )

    client = AsyncQdrantClient(url=settings.QDRANT_URL)

    try:
        log.info("   -> Fetching all vector chunk IDs from Qdrant...")
        all_points, _ = await client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            limit=10000,
            with_payload=["chunk_id"],
            with_vectors=False,
        )

        vector_points_map = {
            p.payload["chunk_id"]: p.id
            for p in all_points
            if p.payload and "chunk_id" in p.payload
        }
        vector_chunk_keys = set(vector_points_map.keys())
        log.info(f"   -> Found {len(vector_chunk_keys)} vectors in Qdrant.")

        orphaned_chunk_keys = list(vector_chunk_keys - known_symbol_keys)

        if not orphaned_chunk_keys:
            console.print(
                "[bold green]✅ No orphaned vectors found. The vector store is clean.[/bold green]"
            )
            return

        console.print(
            f"[yellow]Found {len(orphaned_chunk_keys)} orphaned vectors to prune.[/yellow]"
        )

        point_ids_to_delete = [
            vector_points_map[key]
            for key in orphaned_chunk_keys
            if key in vector_points_map
        ]

        if dry_run:
            console.print(
                "\n[bold yellow]-- DRY RUN: The following vector point IDs would be deleted --[/bold yellow]"
            )
            for point_id in point_ids_to_delete[:20]:
                console.print(f"  - {point_id}")
            if len(point_ids_to_delete) > 20:
                console.print(f"  - ... and {len(point_ids_to_delete) - 20} more.")
            return

        if not point_ids_to_delete:
            console.print(
                "[bold green]✅ No orphaned vectors to prune after filtering.[/bold green]"
            )
            return

        console.print("\n[bold]Pruning orphaned vectors from Qdrant...[/bold]")

        # --- START OF AMENDMENT: Use the correct class for the selector ---
        await client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=PointIdsList(points=point_ids_to_delete),
        )
        # --- END OF AMENDMENT ---

        console.print(
            f"[bold green]✅ Successfully pruned {len(point_ids_to_delete)} orphaned vectors.[/bold green]"
        )

    except Exception as e:
        log.error(f"An error occurred during vector pruning: {e}", exc_info=True)
        raise typer.Exit(code=1)


# ID: 9c0f083b-5653-4c1d-b4bb-f4f38528f062
def main_sync(
    write: bool = typer.Option(
        False, "--write", help="Permanently delete orphaned vectors from Qdrant."
    ),
):
    """Entry point for the Typer command."""
    asyncio.run(_async_main_sync(dry_run=not write))


if __name__ == "__main__":
    typer.run(main_sync)
