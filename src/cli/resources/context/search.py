# src/cli/resources/context/search.py
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
    module_filter: str | None = None
    if path:
        module_filter = path.replace("src/", "").replace("/", ".").strip(".")
    like_pattern = f"%{pattern}%"
    sql = text(
        "\n        SELECT qualname, module, kind, ast_signature, intent\n        FROM core.symbols\n        WHERE (\n            ast_signature ILIKE :pat\n            OR qualname     ILIKE :pat\n            OR intent       ILIKE :pat\n        )\n        AND (CAST(:module_filter AS TEXT) IS NULL OR module ILIKE :module_pat)\n        ORDER BY qualname\n        LIMIT :limit\n        "
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
        logger.info("[yellow]No matches found for:[/yellow] %s", pattern)
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
    logger.info(table)
    if len(rows) == limit:
        logger.info(
            "[dim]Showing first %s results. Use --limit to see more.[/dim]", limit
        )


@app.command("search")
# ID: 6ced2f28-5c2b-410c-b8ec-07db0518b602
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
        logger.info("[red]❌ Error: %s[/red]", e)
        logger.exception("Search failed")
        raise typer.Exit(code=1)
