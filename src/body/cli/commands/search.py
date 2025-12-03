# src/body/cli/commands/search.py
"""
Registers the 'search' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from shared.cli_utils import core_command
from shared.context import CoreContext

from body.cli.logic.hub import hub_search_cmd

console = Console()
search_app = typer.Typer(
    help="Discover capabilities and commands.",
    no_args_is_help=True,
)


@search_app.command("capabilities")
@core_command(dangerous=False)
# ID: 349639a8-ea1a-43f0-9e3b-df205b92aca8
async def search_capabilities_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="The semantic query to search for."),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to return."),
) -> None:
    """
    Performs a semantic search for capabilities in the knowledge base.
    """
    context: CoreContext = ctx.obj

    # JIT wiring is handled by @core_command

    console.print(
        f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
    )

    try:
        cognitive_service = context.cognitive_service
        # cognitive_service.qdrant_service is guaranteed to be initialized by the framework

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
        # Let the framework handle the error display/exit code
        raise RuntimeError(f"Search failed: {e}") from e


@search_app.command("commands")
@core_command(dangerous=False)
# ID: cb2f39e0-7b4a-4134-8996-961c4ceaf517
def search_commands_cmd(
    ctx: typer.Context,
    term: str = typer.Argument(
        ..., help="Term to search in command names/descriptions."
    ),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results."),
) -> None:
    """
    Fuzzy search across CLI commands from the registry.
    """
    # Delegate to logic handler (which might need updating if it uses args)
    # hub_search_cmd is currently defined in body.cli.logic.hub
    # We call it directly. It handles its own DB access via session manager.
    hub_search_cmd(term=term, limit=limit)
