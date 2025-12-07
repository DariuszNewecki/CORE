# src/body/cli/commands/manage/vectors.py
"""
Unified Vector Management Commands

Replaces the scattered vectorization logic with constitutional commands
that use the unified VectorIndexService + domain adapters.

Commands:
- core-admin manage vectors sync policies
- core-admin manage vectors sync patterns
- core-admin manage vectors sync all
"""

from __future__ import annotations

import asyncio

import typer

from services.clients.qdrant_client import QdrantService
from services.vector.adapters.constitutional_adapter import ConstitutionalAdapter
from services.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger


logger = getLogger(__name__)

app = typer.Typer(name="vectors", help="Manage vector collections")


@app.command(name="sync")
# ID: d6711ab9-3a79-47df-957a-59ffc52e947f
def sync_vectors(
    target: str = typer.Argument(
        ...,
        help="What to sync: 'policies', 'patterns', or 'all'",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be vectorized without actually doing it",
    ),
) -> None:
    """
    Synchronize constitutional documents to vector collections.

    This command replaces:
    - core-admin manage policies vectorize
    - core-admin manage patterns vectorize

    Examples:
        core-admin manage vectors sync policies
        core-admin manage vectors sync patterns --dry-run
        core-admin manage vectors sync all
    """
    asyncio.run(_async_sync_vectors(target, dry_run))


async def _async_sync_vectors(target: str, dry_run: bool) -> None:
    """Async implementation of vector sync."""

    valid_targets = {"policies", "patterns", "all"}
    if target not in valid_targets:
        typer.echo(f"❌ Invalid target '{target}'. Must be one of: {valid_targets}")
        raise typer.Exit(1)

    typer.echo("=" * 60)
    typer.echo(f"VECTOR SYNC: {target.upper()}")
    typer.echo("=" * 60)
    typer.echo()

    # Initialize services
    qdrant_service = QdrantService()
    adapter = ConstitutionalAdapter()

    results = {}

    # Sync policies
    if target in {"policies", "all"}:
        typer.echo("📋 Syncing Policies...")
        typer.echo()

        service = VectorIndexService(
            qdrant_service=qdrant_service,  # FIX: Pass service, not .client
            collection_name="core_policies",
        )

        await service.ensure_collection()

        items = adapter.policies_to_items()
        typer.echo(f"  Found {len(items)} policy chunks")

        if not dry_run:
            indexed = await service.index_items(items, batch_size=10)
            typer.echo(f"  ✓ Indexed {len(indexed)} items")
            results["policies"] = len(indexed)
        else:
            typer.echo(f"  [DRY RUN] Would index {len(items)} items")
            results["policies"] = len(items)

        typer.echo()

    # Sync patterns
    if target in {"patterns", "all"}:
        typer.echo("🎨 Syncing Patterns...")
        typer.echo()

        service = VectorIndexService(
            qdrant_service=qdrant_service,  # FIX: Pass service, not .client
            collection_name="core-patterns",
        )

        await service.ensure_collection()

        items = adapter.patterns_to_items()
        typer.echo(f"  Found {len(items)} pattern chunks")

        if not dry_run:
            indexed = await service.index_items(items, batch_size=10)
            typer.echo(f"  ✓ Indexed {len(indexed)} items")
            results["patterns"] = len(indexed)
        else:
            typer.echo(f"  [DRY RUN] Would index {len(items)} items")
            results["patterns"] = len(items)

        typer.echo()

    # Summary
    typer.echo("=" * 60)
    if dry_run:
        typer.echo("DRY RUN COMPLETE")
    else:
        typer.echo("✅ SYNC COMPLETE")

    for collection, count in results.items():
        typer.echo(f"  {collection}: {count} items")
    typer.echo("=" * 60)


@app.command(name="query")
# ID: 26c63756-eb12-4f88-a46b-b0e43d4760b6
def query_vectors(
    collection: str = typer.Argument(
        ...,
        help="Collection to query: 'policies' or 'patterns'",
    ),
    query: str = typer.Argument(..., help="Natural language query"),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to return"),
) -> None:
    """
    Semantic search in vector collections.

    Examples:
        core-admin manage vectors query patterns "atomic action requirements"
        core-admin manage vectors query policies "agent rules" --limit 3
    """
    asyncio.run(_async_query_vectors(collection, query, limit))


async def _async_query_vectors(collection: str, query: str, limit: int) -> None:
    """Async implementation of vector query."""

    collection_map = {
        "policies": "core_policies",
        "patterns": "core-patterns",
    }

    if collection not in collection_map:
        typer.echo(f"❌ Invalid collection. Must be: {list(collection_map.keys())}")
        raise typer.Exit(1)

    qdrant_service = QdrantService()
    service = VectorIndexService(
        qdrant_service=qdrant_service,  # FIX: Pass service instance
        collection_name=collection_map[collection],
    )

    typer.echo(f"🔍 Searching {collection} for: '{query}'")
    typer.echo()

    results = await service.query(query, limit=limit)

    if not results:
        typer.echo("No results found.")
        return

    for i, result in enumerate(results, 1):
        score = result["score"]
        payload = result["payload"]

        typer.echo(f"Result {i} (score: {score:.3f})")
        typer.echo(f"  Doc: {payload.get('doc_id', 'unknown')}")
        typer.echo(f"  Section: {payload.get('section_type', 'unknown')}")
        typer.echo(f"  Content: {payload.get('item_id', 'unknown')[:80]}...")
        typer.echo()


if __name__ == "__main__":
    app()
