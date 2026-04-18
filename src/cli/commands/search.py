# src/cli/commands/search.py
"""
Registers the 'search' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from cli.logic.hub import hub_search_cmd
from cli.utils import core_command
from shared.context import CoreContext


console = Console()
search_app = typer.Typer(
    help="Discover capabilities and commands.", no_args_is_help=True
)


@search_app.command("capabilities")
@core_command(dangerous=False)
# ID: 4df5c462-ba14-4849-b707-ef1fce79b9b4
async def search_capabilities_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="The semantic query to search for."),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to return."),
) -> None:
    """
    Performs a semantic search for capabilities in the knowledge base.
    """
    context: CoreContext = ctx.obj
    logger.info("🧠 Searching for capabilities related to: '[cyan]%s[/cyan]'...", query)
    try:
        cognitive_service = context.cognitive_service
        results = await cognitive_service.search_capabilities(query, limit=limit)
        if not results:
            logger.info("[yellow]No relevant capabilities found.[/yellow]")
            return
        table = Table(title="Top Matching Capabilities")
        table.add_column("Score", style="magenta", justify="right")
        table.add_column("Capability Key", style="cyan")
        table.add_column("Description", style="green")
        for hit in results:
            payload = hit.get("payload", {}) or {}
            key = payload.get("key", "none")
            description = (
                payload.get("description") or "No description provided."
            ).strip()
            score = f"{hit.get('score', 0):.4f}"
            table.add_row(score, key, description)
        logger.info(table)
    except Exception as e:
        raise RuntimeError(f"Search failed: {e}") from e


@search_app.command("commands")
@core_command(dangerous=False)
# ID: 49b5f4fd-7f51-4a19-aa56-7373d83d381d
async def search_commands_cmd(
    ctx: typer.Context,
    term: str = typer.Argument(
        ..., help="Term to search in command names/descriptions."
    ),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results."),
) -> None:
    """
    Fuzzy search across CLI commands from the registry.
    """
    await hub_search_cmd(term=term, limit=limit)
