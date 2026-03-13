# src/cli/resources/vectors/query.py
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
# ID: 44056798-de41-4934-8bba-97e6f88ce1f0
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
    logger.info("[bold cyan]🔍 Querying %s[/bold cyan]", collection)
    logger.info("Query: %s", query)
    console.print()
    try:
        core_context: CoreContext = ctx.obj
        qdrant_service = core_context.qdrant_service or QdrantService()
        collection_name = (
            "core_policies" if collection == "policies" else "core-patterns"
        )
        embedder = CognitiveEmbedderAdapter(core_context.cognitive_service)
        service = VectorIndexService(
            qdrant_service=qdrant_service,
            collection_name=collection_name,
            embedder=embedder,
        )
        results = await service.query(query, limit=limit)
        if not results:
            logger.info("[yellow]No results found[/yellow]")
            return
        logger.info("[bold]Top %s results:[/bold]", len(results))
        logger.info()
        for i, result in enumerate(results, 1):
            score = result.get("score", 0.0)
            content = (
                result.get("content")
                or result.get("text")
                or result.get("payload", {}).get("content")
                or result.get("payload", {}).get("text")
                or ""
            )
            doc_id = (
                result.get("doc_id")
                or result.get("id")
                or result.get("payload", {}).get("doc_id")
                or result.get("payload", {}).get("chunk_id")
                or "Unknown"
            )
            content_preview = content[:200] if content else "[No content available]"
            logger.info("[bold cyan]%s. %s[/bold cyan] (score: %s)", i, doc_id, score)
            logger.info("   %s...", content_preview)
            logger.info()
    except Exception as e:
        logger.error("Vector query failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
