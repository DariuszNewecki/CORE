# src/cli/resources/code/actions.py
from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console
from rich.table import Table

from body.atomic.registry import action_registry
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("actions")
@command_meta(
    canonical_name="code.actions",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="List all registered Atomic Actions showing their IDs, categories, impact levels, and descriptions.",
    dangerous=False,
)
# ID: 4f8e13a3-f017-4d0f-a6ef-340f81d05341
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
    logger.info(table)
