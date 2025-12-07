# src/body/cli/commands/manage/policies.py
"""
Policy management commands for constitutional governance.

Provides commands to vectorize and query constitutional policies
(the Charter) stored in .intent/charter/policies/.

Constitutional Policy: pattern_vectorization.yaml (extends to policies)
"""

from __future__ import annotations

import time

import typer
from rich.console import Console

from services.clients.qdrant_client import QdrantService
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import async_command
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.tools.policy_vectorizer import PolicyVectorizer


logger = getLogger(__name__)
console = Console()

policies_sub_app = typer.Typer(
    help="Manage constitutional policies (vectorization and search).",
    no_args_is_help=True,
)


@atomic_action(
    action_id="manage.vectorize-policies",
    intent="Vectorize constitutional policies for semantic understanding",
    impact=ActionImpact.WRITE_DATA,
    policies=["pattern_vectorization"],  # Reuses the semantic infra policy
    category="governance",
)
# ID: 5f6937cd-fbac-4dd9-8470-4e87a51b5fbd
async def vectorize_policies_internal(
    qdrant_service: QdrantService,
    cognitive_service: CognitiveService,
) -> ActionResult:
    """
    Vectorize all policies from .intent/charter/policies/ into core-policies collection.
    """
    start_time = time.time()

    try:
        vectorizer = PolicyVectorizer(
            repo_root=settings.REPO_PATH,
            cognitive_service=cognitive_service,
            qdrant_service=qdrant_service,
        )

        results = await vectorizer.vectorize_all_policies()

        # Extract values for literal dict construction
        success = results.get("success", False)
        policies_vectorized = results.get("policies_vectorized", 0)
        chunks_created = results.get("chunks_created", 0)
        errors = results.get("errors", [])

        return ActionResult(
            action_id="manage.vectorize-policies",
            ok=success,
            data={
                "success": success,
                "policies_vectorized": policies_vectorized,
                "chunks_created": chunks_created,
                "error_count": len(errors),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_DATA,
            warnings=[str(e) for e in errors] if errors else [],
        )

    except Exception as e:
        return ActionResult(
            action_id="manage.vectorize-policies",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during policy vectorization: {e}"],
        )


@policies_sub_app.command("vectorize")
@async_command
# ID: 4c61c8ec-50c1-485c-89f0-0f9a39c54aeb
async def vectorize_policies_cmd() -> None:
    """
    Vectorize constitutional policies into Qdrant.

    Enables AI agents to perform RAG (Retrieval Augmented Generation)
    against the Constitution to understand rules like "safety_framework"
    or "agent_governance".
    """
    console.print("[cyan]Vectorizing constitutional policies...[/cyan]\n")

    # CLI instantiates services (allowed per DI policy exclusions)
    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=settings.REPO_PATH,
        qdrant_service=qdrant_service,
    )
    # Ensure orchestrator/mind is loaded
    await cognitive_service.initialize()

    result = await vectorize_policies_internal(
        qdrant_service=qdrant_service,
        cognitive_service=cognitive_service,
    )

    if result.ok:
        stats = result.data
        console.print(
            f"[bold green]✓ Vectorized {stats['policies_vectorized']} policies[/bold green]"
        )
        console.print(f"  Total chunks: {stats['chunks_created']}")
        console.print(f"  Duration: {result.duration_sec:.2f}s")

        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in result.warnings:
                console.print(f"  - {w}")
    else:
        error = result.data.get("error", "Unknown error")
        console.print(f"[bold red]✗ Vectorization failed: {error}[/bold red]")
        raise typer.Exit(1)


@policies_sub_app.command("search")
@async_command
# ID: ff1af9c9-6bfe-452c-83a5-0d22d7c55dd7
async def search_policies_cmd(
    query: str = typer.Argument(..., help="Question about the constitution"),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results"),
) -> None:
    """
    Search the constitution semantically.
    """
    console.print(f'[cyan]Searching constitution for: "{query}"[/cyan]\n')

    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=settings.REPO_PATH,
        qdrant_service=qdrant_service,
    )
    await cognitive_service.initialize()

    vectorizer = PolicyVectorizer(
        repo_root=settings.REPO_PATH,
        cognitive_service=cognitive_service,
        qdrant_service=qdrant_service,
    )

    results = await vectorizer.search_policies(query, limit=limit)

    if not results:
        console.print("[yellow]No matching policy rules found.[/yellow]")
        return

    for i, hit in enumerate(results, 1):
        score = hit["score"]
        policy = hit["policy_id"]
        content = hit["content"].replace("\n", " ")[:150] + "..."

        console.print(f"[bold cyan]{i}. {policy}[/bold cyan] ({score:.3f})")
        console.print(f"   {content}")
        console.print()
