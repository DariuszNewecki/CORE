# src/cli/commands/search.py
"""Registers the new, verb-based 'search' command group."""

from __future__ import annotations

import asyncio

import typer
from cli.logic.hub import hub_search
from rich.console import Console
from rich.table import Table
from shared.context import CoreContext

console = Console()
search_app = typer.Typer(
    help="Discover capabilities and commands.",
    no_args_is_help=True,
)


# This is the logic function, now co-located with its command.
# ID: ce6ffa34-2440-4188-bc95-0f6703651b9a
def search_knowledge_command(context: CoreContext, query: str, limit: int = 5) -> None:
    """Synchronous wrapper around async search."""

    async def _run() -> None:
        console.print(
            f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
        )
        try:
            cognitive_service = context.cognitive_service
            results = await cognitive_service.search_capabilities(query, limit=limit)
            if not results:
                console.print("[yellow]No relevant capabilities found.[/yellow]")
                return

            table = Table(title="Top Matching Capabilities")
            table.add_column("Score", style="magenta", justify="right")
            table.add_column("Capability Key", style="cyan")
            table.add_column("Description", style="green")
            for hit in results:
                payload = hit.get("payload", {}) or {}
                key = payload.get("key", "N/A")
                description = (
                    payload.get("description") or "No description provided."
                ).strip()
                score = f"{hit.get('score', 0):.4f}"
                table.add_row(score, key, description)
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]❌ Search failed: {e}[/bold red]")
            raise typer.Exit(code=1)

    asyncio.run(_run())


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
def register(app: typer.Typer, context: CoreContext):
    """Register the 'search' command group to the main CLI app."""

    @search_app.command("capabilities")
    # ID: 22dd2048-ebe7-490b-81f7-632d276585e6
    def search_capabilities_wrapper(
        query: str,
        limit: int = 5,
    ):
        """Performs a semantic search for capabilities in the knowledge base."""
        # This wrapper ensures the context is passed correctly to the logic function.
        search_knowledge_command(context=context, query=query, limit=limit)

    # hub_search does not require context yet, so it can be registered directly
    search_app.command("commands")(hub_search)

    app.add_typer(search_app, name="search")
