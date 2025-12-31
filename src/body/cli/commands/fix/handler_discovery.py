# src/body/cli/commands/fix/handler_discovery.py
"""
Action discovery command - Scans for Atomic Actions in the registry.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from body.atomic.registry import action_registry
from shared.cli_utils import core_command

from . import fix_app


console = Console()


@fix_app.command("discover-actions")  # <--- RENAMED
@core_command(dangerous=False, requires_context=False)
# ID: 01b12a1f-8c71-486a-b2bf-dc6aa887d338
def discover_actions_command(ctx: typer.Context) -> None:
    """
    List all registered Atomic Actions from the canonical registry.
    """
    console.print(
        "[bold cyan]🔍 Discovering Registered Atomic Actions...[/bold cyan]\n"
    )

    actions = action_registry.list_all()

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Action ID", style="cyan")
    table.add_column("Category", style="blue")
    table.add_column("Impact", style="magenta")
    table.add_column("Description")

    for action in sorted(actions, key=lambda x: x.action_id):
        table.add_row(
            action.action_id,
            action.category.value,
            action.impact_level,
            action.description,
        )

    console.print(table)
    console.print(f"\n[green]✅ Total Actions Registered: {len(actions)}[/green]")
