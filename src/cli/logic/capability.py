# src/cli/logic/capability.py
"""
Provides the 'core-admin capability' command group for managing capabilities
in a constitutionally-aligned way. THIS MODULE IS NOW DEPRECATED and will be
removed after the DB-centric migration is complete.
"""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

capability_app = typer.Typer(help="[DEPRECATED] Create and manage capabilities.")


@capability_app.command("new")
# ID: c2111920-a102-52e0-b8f5-1278411d4bae
def capability_new_deprecated():
    """[DEPRECATED] This command is now obsolete. Use 'knowledge sync' instead."""
    console.print(
        "[bold yellow]⚠️  This command is deprecated and will be removed.[/bold yellow]"
    )
    console.print(
        "   -> Please use '[cyan]poetry run core-admin knowledge sync[/cyan]' to synchronize symbols."
    )
