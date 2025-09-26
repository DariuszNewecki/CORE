# src/cli/commands/knowledge.py
"""
Registers the 'knowledge' command group for managing the knowledge base and related artifacts.
"""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from cli.commands.reconcile import reconcile_from_cli
from cli.commands.sync import sync_knowledge_base
from cli.commands.sync_manifest import sync_manifest
from core.cognitive_service import CognitiveService
from features.introspection.export_vectors import export_vectors
from features.introspection.generate_correction_map import generate_maps
from features.introspection.semantic_clusterer import run_clustering
from shared.config import settings

console = Console()
knowledge_app = typer.Typer(
    help="Commands for managing the CORE knowledge base (DB and artifacts)."
)


@knowledge_app.command(
    "search", help="Performs a semantic search for capabilities in the knowledge base."
)
# ID: a4d3f3b1-3e4c-4e8a-9f6b-7c8d9e0a1b2c
# --- THIS IS THE FIX ---
# ID: 66832289-1bc0-48fa-8f8f-2d83fecfe3d9
def search_knowledge_command(
    query: str = typer.Argument(..., help="The natural language search query."),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of results to return."),
):
    """
    A synchronous wrapper that runs the async search_knowledge function.
    """

    async def _search_knowledge_async():
        """
        Finds relevant capabilities by performing a semantic search on the vector database.
        """
        console.print(
            f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
        )
        try:
            cognitive_service = CognitiveService(settings.REPO_PATH)
            results = await cognitive_service.search_capabilities(query, limit=limit)

            if not results:
                console.print("[yellow]No relevant capabilities found.[/yellow]")
                return

            table = Table(title="Top Matching Capabilities")
            table.add_column("Score", style="magenta", justify="right")
            table.add_column("Capability Key", style="cyan")
            table.add_column("Description", style="green")

            for hit in results:
                payload = hit.get("payload", {})
                key = payload.get("key", "N/A")
                description = (
                    payload.get("description") or "No description provided."
                ).strip()
                score = f"{hit.get('score', 0):.4f}"
                table.add_row(score, key, description)

            console.print(table)

        except Exception as e:
            console.print(
                f"[bold red]❌ An error occurred during the search: {e}[/bold red]"
            )
            raise typer.Exit(code=1)

    asyncio.run(_search_knowledge_async())


# --- END OF FIX ---


# --- Primary Commands ---
knowledge_app.command(
    "sync",
    help="Scans the codebase and syncs all symbols to the database.",
)(sync_knowledge_base)

knowledge_app.command(
    "reconcile-from-cli",
    help="Links capabilities in the DB using the CLI registry as a map.",
)(reconcile_from_cli)

knowledge_app.command(
    "sync-manifest",
    help="Synchronizes project_manifest.yaml with public capabilities from the database.",
)(sync_manifest)

# --- Analysis & Reporting Commands ---
knowledge_app.command(
    "export-vectors", help="Exports all vectors from Qdrant to a JSONL file."
)(export_vectors)
knowledge_app.command(
    "cluster-vectors", help="Clusters exported vectors to find semantic domains."
)(run_clustering)
knowledge_app.command(
    "generate-map",
    help="Generates alias maps from clustering results.",
)(generate_maps)


# ID: c75e151b-1569-46a1-b809-d2c7c46922d9
def register(app: typer.Typer):
    """Register the 'knowledge' command group with the main CLI app."""
    app.add_typer(knowledge_app, name="knowledge")
