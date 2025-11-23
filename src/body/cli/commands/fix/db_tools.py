# src/body/cli/commands/fix/db_tools.py
"""
Database and vector-related commands for the 'fix' CLI group.

Provides:
- fix db-registry
- fix vector-sync (replaces orphaned-vectors + dangling-vector-links)
"""

from __future__ import annotations

import typer

from features.maintenance.command_sync_service import _sync_commands_to_db
from features.self_healing.sync_vectors import main_sync as sync_vectors
from shared.cli_utils import async_command

from . import (
    _confirm_dangerous_operation,
    _run_with_progress,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
@handle_command_errors
@async_command
# ID: 0156169d-4675-4811-8118-1b94c3a03797
async def sync_db_registry_command() -> None:
    """CLI wrapper for the command sync service."""
    from body.cli.admin_cli import app as main_app

    with console.status("[cyan]Syncing CLI commands to database...[/cyan]"):
        await _sync_commands_to_db(main_app)
    console.print("[green]✅ Database registry sync completed[/green]")


@fix_app.command(
    "vector-sync",
    help="Atomically synchronize vectors between PostgreSQL and Qdrant.",
)
@handle_command_errors
# ID: 3a7f9c2e-5b8d-4f1a-9e6c-1d2b4a8f7e3c
def fix_vector_sync_command(
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes to both PostgreSQL and Qdrant (otherwise dry-run).",
    ),
) -> None:
    """
    Atomic bidirectional vector synchronization.

    This performs two operations in correct order:
    1. Prune orphaned vectors from Qdrant (vectors without DB links)
    2. Prune dangling links from PostgreSQL (links to missing vectors)

    Running both operations atomically prevents partial sync states and
    ensures consistency between the vector store and the main database.
    """
    if not _confirm_dangerous_operation("vector-sync", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    _run_with_progress(
        "Synchronizing vector database",
        lambda: sync_vectors(write=write, dry_run=not write),
    )
    console.print("[green]✅ Vector synchronization completed[/green]")
