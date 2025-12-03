# src/body/cli/commands/manage/patterns.py
"""
Pattern management commands for constitutional governance.

Provides commands to vectorize, query, and validate architectural patterns.

Constitutional Policy: pattern_vectorization.yaml
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from features.introspection.pattern_vectorizer import PatternVectorizer
from rich.console import Console
from rich.table import Table
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import async_command
from shared.config import settings

if TYPE_CHECKING:
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

console = Console()

patterns_sub_app = typer.Typer(
    help="Manage constitutional patterns",
    no_args_is_help=True,
)


@atomic_action(
    action_id="manage.vectorize-patterns",
    intent="Vectorize constitutional patterns for semantic understanding",
    impact=ActionImpact.WRITE_DATA,
    policies=["pattern_vectorization"],
    category="patterns",
)
# ID: c13c66ca-5107-4a57-b36b-6bb499991afc
async def vectorize_patterns_internal(
    qdrant_service: QdrantService,
    cognitive_service: CognitiveService,
) -> ActionResult:
    """
    Vectorize all patterns from .intent/charter/patterns/ into core-patterns collection.

    Constitutional: Follows dependency_injection_policy - services injected, not instantiated.

    Args:
        qdrant_service: Injected Qdrant service
        cognitive_service: Injected cognitive service

    Returns:
        ActionResult with:
        - ok: True if successful
        - data: {
            "patterns_processed": int,
            "total_chunks": int,
            "results": dict[pattern_id -> chunk_count],
          }
    """
    import time

    start_time = time.time()

    try:
        # Initialize pattern vectorizer with injected services
        vectorizer = PatternVectorizer(
            qdrant_service=qdrant_service,
            cognitive_service=cognitive_service,
        )

        # Vectorize all patterns
        # FIX: Added 'await' here
        results = await vectorizer.vectorize_all_patterns()

        total_chunks = sum(results.values())

        return ActionResult(
            action_id="manage.vectorize-patterns",
            ok=True,
            data={
                "patterns_processed": len(results),
                "total_chunks": total_chunks,
                "results": results,
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_DATA,
        )

    except Exception as e:
        return ActionResult(
            action_id="manage.vectorize-patterns",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during pattern vectorization: {e}"],
        )


@patterns_sub_app.command(
    "vectorize",
    help="Vectorize constitutional patterns for semantic understanding",
)
@async_command
# ID: 599bf1ee-623c-4c94-b3c9-6c4a236ad67e
async def vectorize_patterns_cmd() -> None:
    """
    CLI wrapper for pattern vectorization.

    Vectorizes all pattern files from .intent/charter/patterns/ into
    the core-patterns Qdrant collection for semantic queries.

    Constitutional: CLI is allowed to instantiate services per DI policy exclusions.
    """
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    console.print("[cyan]Vectorizing constitutional patterns...[/cyan]\n")

    # CLI instantiates services (allowed per DI policy)
    qdrant_service = QdrantService()

    # FIX: Changed 'repo_root' to 'repo_path' to match CognitiveService.__init__
    cognitive_service = CognitiveService(
        repo_path=settings.REPO_PATH,
        qdrant_service=qdrant_service,
    )

    # Call internal function with injected services
    result = await vectorize_patterns_internal(
        qdrant_service=qdrant_service,
        cognitive_service=cognitive_service,
    )

    if result.ok:
        patterns = result.data["patterns_processed"]
        chunks = result.data["total_chunks"]
        duration = result.duration_sec

        console.print(f"[bold green]✓ Vectorized {patterns} patterns[/bold green]")
        console.print(f"  Total chunks: {chunks}")
        console.print(f"  Duration: {duration:.2f}s\n")

        # Show breakdown
        if result.data.get("results"):
            table = Table(title="Pattern Vectorization Results")
            table.add_column("Pattern", style="cyan")
            table.add_column("Chunks", justify="right", style="green")

            for pattern_id, chunk_count in result.data["results"].items():
                table.add_row(pattern_id, str(chunk_count))

            console.print(table)
    else:
        error = result.data.get("error", "Unknown error")
        console.print(f"[bold red]✗ Vectorization failed: {error}[/bold red]")


@atomic_action(
    action_id="manage.query-pattern",
    intent="Query constitutional patterns semantically",
    impact=ActionImpact.READ_ONLY,
    policies=["pattern_vectorization"],
    category="patterns",
)
# ID: 5b64ee0f-fd78-4118-bc32-c7ab6edca79d
async def query_pattern_internal(
    query: str,
    qdrant_service: QdrantService,
    cognitive_service: CognitiveService,
    limit: int = 5,
) -> ActionResult:
    """
    Query patterns semantically using natural language.

    Constitutional: Follows dependency_injection_policy - services injected, not instantiated.

    Args:
        query: Natural language question about patterns
        qdrant_service: Injected Qdrant service
        cognitive_service: Injected cognitive service
        limit: Maximum number of results

    Returns:
        ActionResult with matching pattern chunks
    """
    import time

    start_time = time.time()

    try:
        vectorizer = PatternVectorizer(
            qdrant_service=qdrant_service,
            cognitive_service=cognitive_service,
        )

        results = await vectorizer.query_pattern(query, limit=limit)

        return ActionResult(
            action_id="manage.query-pattern",
            ok=True,
            data={
                "query": query,
                "results_count": len(results),
                "results": results,
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
        )

    except Exception as e:
        return ActionResult(
            action_id="manage.query-pattern",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during pattern query: {e}"],
        )


@patterns_sub_app.command(
    "query",
    help="Query constitutional patterns semantically",
)
@async_command
# ID: 763036b7-9591-4ef1-8156-af61553857c5
async def query_pattern_cmd(
    query: str = typer.Argument(..., help="Natural language query about patterns"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum results to return"),
) -> None:
    """
    CLI wrapper for pattern queries.

    Constitutional: CLI is allowed to instantiate services per DI policy exclusions.

    Examples:
        core-admin manage patterns query "what does atomic_actions require?"
        core-admin manage patterns query "workflow orchestration rules"
    """
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

    console.print(f'[cyan]Querying patterns: "{query}"[/cyan]\n')

    # CLI instantiates services (allowed per DI policy)
    qdrant_service = QdrantService()

    # FIX: Changed 'repo_root' to 'repo_path' to match CognitiveService.__init__
    cognitive_service = CognitiveService(
        repo_path=settings.REPO_PATH,
        qdrant_service=qdrant_service,
    )

    # Call internal function with injected services
    result = await query_pattern_internal(
        query=query,
        qdrant_service=qdrant_service,
        cognitive_service=cognitive_service,
        limit=limit,
    )

    if result.ok:
        results = result.data["results"]

        if not results:
            console.print("[yellow]No matching patterns found.[/yellow]")
            return

        console.print(f"[bold]Found {len(results)} matches:[/bold]\n")

        for i, match in enumerate(results, 1):
            score = match["score"]
            pattern_id = match["pattern_id"]
            section_path = match["section_path"]
            content = (
                match["content"][:200] + "..."
                if len(match["content"]) > 200
                else match["content"]
            )

            console.print(f"[bold cyan]{i}. {pattern_id}[/bold cyan] ({score:.3f})")
            console.print(f"   Section: {section_path}")
            console.print(f"   {content}")
            console.print()
    else:
        error = result.data.get("error", "Unknown error")
        console.print(f"[bold red]✗ Query failed: {error}[/bold red]")
