# src/body/cli/commands/manage/vectors.py
# ID: cli.commands.manage.vectors
"""
Unified Vector Management Commands

Constitutional pattern: resource-action with --write flag
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

app = typer.Typer(
    name="vectors", help="Manage vector collections", no_args_is_help=True
)


@app.command(name="sync")
@core_command(requires_context=False, dangerous=True)
# ID: d6711ab9-3a79-47df-957a-59ffc52e947f
async def sync_vectors(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes (default: dry-run)",
    ),
    target: str = typer.Option(
        "all",
        "--target",
        "-t",
        help="What to sync: 'policies', 'patterns', or 'all'",
    ),
) -> None:
    """
    Synchronize constitutional documents to vector collections.

    Examples:
        # Dry-run all targets
        core-admin manage vectors sync

        # Sync policies only
        core-admin manage vectors sync --write --target policies

        # Sync patterns only
        core-admin manage vectors sync --write --target patterns

        # Sync all (policies + patterns)
        core-admin manage vectors sync --write
    """
    console.print("[bold cyan]🧠 Vector Synchronization[/bold cyan]")
    console.print(f"Target: {target}")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    console.print()

    valid_targets = {"policies", "patterns", "all"}
    if target not in valid_targets:
        console.print(
            f"[red]❌ Invalid target '{target}'. Must be one of: {valid_targets}[/red]",
            err=True,
        )
        raise typer.Exit(1)

    try:
        # Initialize services
        qdrant_service = QdrantService()
        adapter = ConstitutionalAdapter()

        results = {}

        # Sync policies
        if target in {"policies", "all"}:
            console.print("📋 Syncing Policies...")

            service = VectorIndexService(
                qdrant_service=qdrant_service,
                collection_name="core_policies",
            )

            await service.ensure_collection()
            items = adapter.policies_to_items()
            console.print(f"  Found {len(items)} policy chunks")

            if write:
                indexed = await service.index_items(items, batch_size=10)
                console.print(f"  ✅ Indexed {len(indexed)} items")
                results["policies"] = len(indexed)
            else:
                console.print(f"  [DRY-RUN] Would index {len(items)} items")
                results["policies"] = len(items)

            console.print()

        # Sync patterns
        if target in {"patterns", "all"}:
            console.print("🎨 Syncing Patterns...")

            service = VectorIndexService(
                qdrant_service=qdrant_service,
                collection_name="core-patterns",
            )

            await service.ensure_collection()
            items = adapter.patterns_to_items()
            console.print(f"  Found {len(items)} pattern chunks")

            if write:
                indexed = await service.index_items(items, batch_size=10)
                console.print(f"  ✅ Indexed {len(indexed)} items")
                results["patterns"] = len(indexed)
            else:
                console.print(f"  [DRY-RUN] Would index {len(items)} items")
                results["patterns"] = len(items)

            console.print()

        # Summary
        if write:
            console.print("[green]✅ Sync completed[/green]")
        else:
            console.print("[yellow]DRY-RUN completed (use --write to apply)[/yellow]")

        for collection, count in results.items():
            console.print(f"  {collection}: {count} items")

    except Exception as e:
        logger.error("Vector sync failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)


@app.command(name="query")
@core_command(requires_context=False)
# ID: 26c63756-eb12-4f88-a46b-b0e43d4760b6
async def query_vectors(
    query: str = typer.Argument(..., help="Natural language query"),
    collection: str = typer.Option(
        "policies",
        "--collection",
        "-c",
        help="Collection to query: 'policies' or 'patterns'",
    ),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to return"),
) -> None:
    """
    Semantic search in vector collections.

    Examples:
        # Search policies
        core-admin manage vectors query "file access rules"

        # Search patterns with limit
        core-admin manage vectors query "atomic actions" --collection patterns --limit 3
    """
    console.print(f"[bold cyan]🔍 Querying {collection}[/bold cyan]")
    console.print(f"Query: {query}")
    console.print()

    try:
        qdrant_service = QdrantService()
        collection_name = (
            "core_policies" if collection == "policies" else "core-patterns"
        )

        service = VectorIndexService(
            qdrant_service=qdrant_service,
            collection_name=collection_name,
        )

        results = await service.search(query, limit=limit)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"[bold]Top {len(results)} results:[/bold]")
        console.print()

        for i, result in enumerate(results, 1):
            score = result.get("score", 0.0)
            content = result.get("content", "N/A")
            metadata = result.get("metadata", {})

            console.print(f"{i}. [bold cyan]Score: {score:.3f}[/bold cyan]")
            console.print(f"   {content[:200]}...")
            if metadata:
                console.print(f"   Metadata: {metadata}")
            console.print()

    except Exception as e:
        logger.error("Vector query failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
