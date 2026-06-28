# src/cli/commands/commands.py

"""commands resource — fuzzy search across registered CLI commands.

Replaces the former `search commands` command (renamed to
`commands search` to satisfy cli.standard_verbs: resource.action).
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()
commands_app = typer.Typer(
    help="Search and inspect registered CLI commands.", no_args_is_help=True
)


@commands_app.command("search")
@core_command(dangerous=False, requires_context=False)
# ID: 8b2d4f67-a1c3-4e9b-b572-6d0e3a7f2c85
async def commands_search_cmd(
    ctx: typer.Context,
    term: str = typer.Argument(
        ..., help="Term to search in command names/descriptions."
    ),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results."),
) -> None:
    """Fuzzy search across CLI commands via /v1/search/commands."""
    _ = ctx
    console.print(f"🔍 Searching CLI commands for: '[cyan]{term}[/cyan]'...")
    client = CoreApiClient()
    payload = await client.inspect_search_commands(q=term, limit=limit)
    if not payload.get("available", False):
        error = payload.get("error", "unknown error")
        console.print(f"[yellow]Search unavailable: {error}[/yellow]")
        return
    results = payload.get("results") or []
    if not results:
        console.print("[yellow]No matching commands found.[/yellow]")
        return
    table = Table(title=f"Matching Commands ({len(results)})")
    table.add_column("Command", style="cyan")
    table.add_column("Module", style="magenta")
    table.add_column("Description", style="green")
    for hit in results:
        description = (hit.get("description") or "").strip() or "—"
        if len(description) > 100:
            description = description[:99] + "…"
        table.add_row(
            hit.get("command", "—"),
            hit.get("module", "—"),
            description,
        )
    console.print(table)
