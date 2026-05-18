# src/cli/commands/fix/handler_discovery.py
"""
Action discovery command — thin client over GET /v1/actions.

Renders the full atomic-action registry server-side; the CLI just shapes
the table.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command("discover-actions")
@core_command(dangerous=False, requires_context=False)
# ID: a5ba0fda-a697-490f-8a81-f16056b380c4
async def discover_actions_command(ctx: typer.Context) -> None:
    """
    List all registered Atomic Actions from the canonical registry.
    """
    _ = ctx
    console.print(
        "[bold cyan]🔍 Discovering Registered Atomic Actions...[/bold cyan]\n"
    )
    client = CoreApiClient()
    payload = await client.list_actions()
    actions = payload.get("actions", [])
    table = Table(show_header=True, header_style="bold green")
    table.add_column("Action ID", style="cyan")
    table.add_column("Category", style="blue")
    table.add_column("Impact", style="magenta")
    table.add_column("Description")
    for action in sorted(actions, key=lambda a: a.get("action_id", "")):
        table.add_row(
            action.get("action_id", ""),
            action.get("category", ""),
            action.get("impact_level", ""),
            action.get("description", ""),
        )
    console.print(table)
    console.print(f"\n[green]✅ Total Actions Registered: {len(actions)}[/green]")
