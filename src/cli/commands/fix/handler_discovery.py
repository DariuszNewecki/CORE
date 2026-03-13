# src/cli/commands/fix/handler_discovery.py
"""
Action discovery command - Scans for Atomic Actions in the registry.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from body.atomic.registry import action_registry
from shared.cli_utils import core_command

from . import fix_app


console = Console()


@fix_app.command("discover-actions")
@core_command(dangerous=False, requires_context=False)
# ID: a5ba0fda-a697-490f-8a81-f16056b380c4
def discover_actions_command(ctx: typer.Context) -> None:
    """
    List all registered Atomic Actions from the canonical registry.
    """
    logger.info("[bold cyan]🔍 Discovering Registered Atomic Actions...[/bold cyan]\n")
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
    logger.info(table)
    logger.info("\n[green]✅ Total Actions Registered: %s[/green]", len(actions))
