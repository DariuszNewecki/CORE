# src/cli/commands/knowledge_sync.py
"""
CLI command for synchronizing operational knowledge from YAML files to the database.
"""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()


# ID: 416af662-de55-4da5-8e73-5e8255e842de
def sync_operational(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the database."
    )
):
    """
    One-way sync of operational knowledge (CLI, Roles, Resources) from YAML to DB.
    """
    if not write:
        console.print(
            "[bold yellow]-- DRY RUN --[/bold yellow]\n"
            "This command will read operational YAML files and show what would be synced.\n"
            "Run with '--write' to apply changes to the database."
        )
        return

    asyncio.run(sync_operational())


# ID: 41e17c9c-abfb-4af2-9421-412f8c688bfc
def register(app: typer.Typer):
    """Register the 'knowledge sync-operational' command."""
    # Find the 'knowledge' command group if it exists
    knowledge_app_group = next(
        (g for g in app.registered_groups if g.name == "knowledge"), None
    )

    if knowledge_app_group:
        knowledge_app = knowledge_app_group.typer_instance
        knowledge_app.command("sync-operational")(sync_operational)
