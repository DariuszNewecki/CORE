# src/cli/commands/capability.py
"""
Provides the 'core-admin capability' command group for managing capabilities
in a constitutionally-aligned way. THIS MODULE IS NOW DEPRECATED and will be
removed after the DB-centric migration is complete.
"""

from __future__ import annotations

import typer
from rich.console import Console

# --- FIX: This command is obsolete and its logic has been moved. ---
# We are commenting it out to fix the import error.
# from .commands.capability.migrate import migrate_to_uuids

console = Console()

capability_app = typer.Typer(help="[DEPRECATED] Create and manage capabilities.")


@capability_app.command("new")
# ID: 628f3738-0aca-4abb-a267-0d1c4a890e5d
def capability_new_deprecated():
    """[DEPRECATED] This command is now obsolete. Use 'knowledge sync' instead."""
    console.print(
        "[bold yellow]⚠️  This command is deprecated and will be removed.[/bold yellow]"
    )
    console.print(
        "   -> Please use '[cyan]poetry run core-admin knowledge sync[/cyan]' to synchronize symbols."
    )


# --- FIX: The migrate-tags command is also obsolete. ---
# @capability_app.command(
#     "migrate-tags",
#     help="[DEPRECATED] Migrates legacy string-based capabilities to stable UUIDs in the DB.",
# )(migrate_to_uuids)


# ID: d90ea0b5-b563-4508-9b1c-1c7c58789141
def register(app: typer.Typer):
    """Register the 'capability' command group with the main CLI app."""
    app.add_typer(capability_app, name="capability")
