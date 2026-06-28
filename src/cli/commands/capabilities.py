# src/cli/commands/capabilities.py

"""capabilities resource — semantic search for CORE capability entries.

Replaces the former `search capabilities` command (renamed to
`capabilities search` to satisfy cli.standard_verbs: resource.action).
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
capabilities_app = typer.Typer(
    help="Inspect and search CORE capabilities.", no_args_is_help=True
)


@capabilities_app.command("search")
@core_command(dangerous=False, requires_context=False)
# ID: 3a7f91c2-e4b5-4d8a-b063-5e2f0a1c8d94
async def capabilities_search_cmd(
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
