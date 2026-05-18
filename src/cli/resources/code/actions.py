# src/cli/resources/code/actions.py
import logging

from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = logging.getLogger(__name__)
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
async def list_actions_cmd() -> None:
    """
    List all registered Atomic Actions (Body Capabilities).
    Shows IDs, categories, and impact levels for autonomous building blocks.
    """
    client = CoreApiClient()
    payload = await client.list_actions()
    actions = payload.get("actions", [])
    table = Table(title="Registered Atomic Actions", header_style="bold green")
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
