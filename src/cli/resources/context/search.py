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
from rich.table import Table
from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


async def _search_async(pattern: str, path: str | None, limit: int) -> None:
    """Query core.symbols for qualname/ast_signature matches."""
    service_registry.prime(get_session)

    # Build module filter from path argument
    module_filter: str | None = None
    if path:
        module_filter = path.replace("src/", "").replace("/", ".").strip(".")

    like_pattern = f"%{pattern}%"

    sql = text(
        """
        SELECT qualname, module, kind, ast_signature, intent
        FROM core.symbols
        WHERE (
            ast_signature ILIKE :pat
            OR qualname     ILIKE :pat
            OR intent       ILIKE :pat
        )
        AND (:module_filter IS NULL OR module ILIKE :module_pat)
        ORDER BY qualname
        LIMIT :limit
        """
    )

    async with get_session() as session:
        result = await session.execute(
            sql,
            {
                "pat": like_pattern,
                "module_filter": module_filter,
                "module_pat": f"{module_filter}%" if module_filter else None,
                "limit": limit,
            },
        )
        rows = result.fetchall()

    if not rows:
        console.print(f"[yellow]No matches found for:[/yellow] {pattern}")
        return

    table = Table(
        title=f"Search results for '{pattern}' ({len(rows)} found)",
        header_style="bold cyan",
    )
    table.add_column("Symbol", style="cyan")
    table.add_column("Module", style="dim")
    table.add_column("Kind", style="magenta")
    table.add_column("Signature / Intent", style="green")

    for row in rows:
        summary = (row.intent or row.ast_signature or "—")[:80]
        table.add_row(row.qualname, row.module, row.kind, summary)

    console.print(table)
    if len(rows) == limit:
        console.print(
            f"[dim]Showing first {limit} results. Use --limit to see more.[/dim]"
        )


# ID: 48e206a5-a79f-4dfd-ada4-6e3154ec7040
@app.command("search")
# ID: 043f6c37-c919-447e-9a4b-eaca01e6d609
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
    Queries the symbols table directly (qualname, signature, intent).

    Examples:
        core-admin context search isinstance
        core-admin context search "async def" --path src/will
        core-admin context search "try" --limit 10

    For semantic/vector search, use 'core-admin context build' instead.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return

    try:
        asyncio.run(_search_async(pattern, path, limit))
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Search failed")
        raise typer.Exit(code=1)
