# src/cli/commands/fix/list_commands.py
"""
Listing and discovery commands for the 'fix' CLI group.

Provides:
- core-admin fix list — thin client over GET /v1/fix/commands.

Renders the registered fix-* atomic actions returned by the server
(action_id, category, impact, description) rather than the local CLI
COMMAND_CONFIG used pre-migration. The two views are not identical;
this is the intentional behavior per ADR-055 D6 Batch C4 ("CLI is a
typed HTTP client").
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command("list", help="List all available fix commands with their categories.")
# ID: cf22c003-eec0-4c68-8bac-f7876a276538
async def list_commands() -> None:
    """
    Render a Rich table of all registered fix-category atomic actions.

    Columns: Action ID, Category, Impact, Description.
    """
    client = CoreApiClient()
    payload = await client.list_fix_commands()
    commands = payload.get("commands", [])
    table = Table(title="Available fix actions")
    table.add_column("Action ID", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Impact", justify="center")
    table.add_column("Description", style="dim")
    for cmd in sorted(commands, key=lambda c: c.get("action_id", "")):
        table.add_row(
            cmd.get("action_id", ""),
            cmd.get("category", ""),
            cmd.get("impact_level", ""),
            cmd.get("description", ""),
        )
    console.print(table)
