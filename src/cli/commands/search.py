# src/cli/commands/search.py

"""Search command group — capabilities and commands, both via API.

Per ADR-057 D5 (revised 2026-05-18) and #363 (closed 2026-05-19):
- `search capabilities` is served by GET /v1/search/capabilities.
- `search commands` is served by GET /v1/search/commands.
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
search_app = typer.Typer(
    help="Discover capabilities and commands.", no_args_is_help=True
)


@search_app.command("capabilities")
@core_command(dangerous=False, requires_context=False)
# ID: 4df5c462-ba14-4849-b707-ef1fce79b9b4
async def search_capabilities_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="The semantic query to search for."),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to return."),
) -> None:
    """Performs a semantic search for capabilities via /v1/search/capabilities."""
    _ = ctx
    console.print(
        f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
    )
    client = CoreApiClient()
    payload = await client.inspect_search_capabilities(q=query, limit=limit)
    if not payload.get("available", False):
        error = payload.get("error", "unknown error")
        console.print(f"[yellow]Search unavailable: {error}[/yellow]")
        return
    results = payload.get("results") or []
    if not results:
        console.print("[yellow]No relevant capabilities found.[/yellow]")
        return
    table = Table(title="Top Matching Capabilities")
    table.add_column("Score", style="magenta", justify="right")
    table.add_column("Capability Key", style="cyan")
    table.add_column("Description", style="green")
    for hit in results:
        hit_payload = hit.get("payload", {}) or {}
        key = hit_payload.get("key", "none")
        description = (
            hit_payload.get("description") or "No description provided."
        ).strip()
        score = f"{hit.get('score', 0):.4f}"
        table.add_row(score, key, description)
    console.print(table)


@search_app.command("commands")
@core_command(dangerous=False, requires_context=False)
# ID: 49b5f4fd-7f51-4a19-aa56-7373d83d381d
async def search_commands_cmd(
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
