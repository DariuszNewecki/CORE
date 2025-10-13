# src/cli/logic/sync.py
"""
Implements the 'knowledge sync' command, the single source of truth for
synchronizing the codebase state (IDs) with the database.
"""

from __future__ import annotations

import asyncio

import typer
from features.introspection.sync_service import run_sync_with_db
from rich.console import Console

console = Console()


async def _async_sync_knowledge(write: bool):
    """Core async logic for the sync command."""
    console.print(
        "[bold cyan]🚀 Synchronizing codebase state with database using temp table strategy...[/bold cyan]"
    )

    if not write:
        console.print(
            "\n[bold yellow]💧 Dry Run: This command no longer supports a dry run due to its database-centric logic.[/bold yellow]"
        )
        console.print("   Run with '--write' to execute the synchronization.")
        return

    stats = await run_sync_with_db()

    console.print("\n--- Knowledge Sync Summary ---")
    console.print(f"   Scanned from code:  [cyan]{stats['scanned']}[/cyan] symbols")
    console.print(f"   New symbols added:  [green]{stats['inserted']}[/green]")
    console.print(f"   Existing symbols updated: [yellow]{stats['updated']}[/yellow]")
    console.print(f"   Obsolete symbols removed: [red]{stats['deleted']}[/red]")
    console.print(
        "\n[bold green]✅ Database is now synchronized with the codebase.[/bold green]"
    )


# ID: 89517800-0799-476e-8078-a184519a76a1
def sync_knowledge_base(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the database."
    ),
):
    """Scans the codebase and syncs all symbols and their IDs to the database."""
    asyncio.run(_async_sync_knowledge(write))
