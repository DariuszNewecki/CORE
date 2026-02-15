# src/body/cli/resources/context/search.py
"""
Context search command - Direct pattern search.

Fast path for simple code pattern searches without full context building.

Usage:
    core-admin context search isinstance
    core-admin context search "async def" --path src/will
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


async def _search_async(pattern: str, path: str | None, limit: int) -> None:
    """Async implementation of search command."""
    console.print(f"[bold blue]🔍 Searching for:[/bold blue] {pattern}")

    if path:
        console.print(f"[dim]Limiting to path: {path}[/dim]")

    # Bootstrap
    core_context = create_core_context(service_registry)
    service_registry.prime(get_session)

    # TODO: Implement direct pattern search in DBProvider
    # This would be a fast SQL query like:
    # SELECT qualname, file_path FROM core.symbols
    # WHERE ast_signature LIKE '%isinstance%' OR calls::jsonb ? 'isinstance'
    # LIMIT 20

    console.print("[yellow]⚠️  Direct search not yet implemented[/yellow]")
    console.print(f"[dim]Use: core-admin context build '{pattern}' instead[/dim]")
    console.print("")
    console.print("[dim]Suggested implementation:[/dim]")
    console.print("[dim]  - Add pattern_search() method to DBProvider[/dim]")
    console.print("[dim]  - Query symbols table for matching patterns[/dim]")
    console.print("[dim]  - Return lightweight results without full context[/dim]")


# ID: 48e206a5-a79f-4dfd-ada4-6e3154ec7040
def search(
    pattern: str = typer.Argument(
        ..., help="Code pattern to search (e.g., 'isinstance')"
    ),
    path: str = typer.Option(None, "--path", help="Limit search to specific path"),
    limit: int = typer.Option(20, "--limit", help="Maximum results to return"),
) -> None:
    """
    Search for code patterns directly in the knowledge graph.

    Faster than 'build' for simple pattern searches.
    Uses database queries without LLM context building.

    Examples:
        core-admin context search isinstance
        core-admin context search "async def" --path src/will
        core-admin context search "try" --limit 10

    Note: This is a fast path that queries the database directly.
    For semantic understanding, use 'core-admin context build' instead.
    """
    try:
        # Run async function in sync context (Typer requirement)
        asyncio.run(_search_async(pattern, path, limit))

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Search failed")
        raise typer.Exit(code=1)
