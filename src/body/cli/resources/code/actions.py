# src/body/cli/resources/code/actions.py
from rich.console import Console
from rich.table import Table

from body.atomic.registry import action_registry

from .hub import app


console = Console()


@app.command("actions")
# ID: c006ad04-157c-4ed5-8301-95e656a982c8
def list_actions_cmd():
    """
    List all registered Atomic Actions (Body Capabilities).
    Shows IDs, categories, and impact levels for autonomous building blocks.
    """
    actions = action_registry.list_all()

    table = Table(title="Registered Atomic Actions", header_style="bold green")
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
