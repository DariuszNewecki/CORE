# src/body/cli/resources/vectors/query.py
# ID: e1c3aa5b-ef6b-4d3d-989e-614e51724c82
"""
Vector query command.

Semantic search in vector collections.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("query")
@core_command(requires_context=True)
# ID: 26c63756-eb12-4f88-a46b-b0e43d4760b6
async def query_vectors(
    ctx: typer.Context,
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

    Search constitutional documents using natural language queries.

    Examples:
        # Search policies
        core-admin vectors query "file access rules"

        # Search patterns with limit
        core-admin vectors query "atomic actions" --collection patterns --limit 3

        # Search both
        core-admin vectors query "governance" --collection policies
    """
    console.print(f"[bold cyan]🔍 Querying {collection}[/bold cyan]")
    console.print(f"Query: {query}")
    console.print()

    try:
        # Get CoreContext which has CognitiveService
        core_context: CoreContext = ctx.obj

        # Use QdrantService from context if available, otherwise create new
        qdrant_service = core_context.qdrant_service or QdrantService()

        # Map collection name
        collection_name = (
            "core_policies" if collection == "policies" else "core-patterns"
        )

        # Use the existing CognitiveEmbedderAdapter
        embedder = CognitiveEmbedderAdapter(core_context.cognitive_service)

        # Create VectorIndexService with embedder
        service = VectorIndexService(
            qdrant_service=qdrant_service,
            collection_name=collection_name,
            embedder=embedder,
        )

        # Perform search
        results = await service.query(query, limit=limit)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"[bold]Top {len(results)} results:[/bold]")
        console.print()

        for i, result in enumerate(results, 1):
            # Extract fields - results may have different structures
            score = result.get("score", 0.0)

            # Try various field names for content
            content = (
                result.get("content")
                or result.get("text")
                or result.get("payload", {}).get("content")
                or result.get("payload", {}).get("text")
                or ""
            )

            # Try various field names for document ID
            doc_id = (
                result.get("doc_id")
                or result.get("id")
                or result.get("payload", {}).get("doc_id")
                or result.get("payload", {}).get("chunk_id")
                or "Unknown"
            )

            # Truncate content
            content_preview = content[:200] if content else "[No content available]"

            console.print(f"[bold cyan]{i}. {doc_id}[/bold cyan] (score: {score:.3f})")
            console.print(f"   {content_preview}...")
            console.print()

    except Exception as e:
        logger.error("Vector query failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)
