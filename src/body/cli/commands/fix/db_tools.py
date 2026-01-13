# src/body/cli/commands/fix/db_tools.py
"""
Database and vector-related commands for the 'fix' CLI group.

Refactored to use the Constitutional CLI Framework (@core_command).
CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Synchronizes local CLI structure and vectors with the Mind (DB/Qdrant).
"""

from __future__ import annotations

import typer

from features.maintenance.command_sync_service import _sync_commands_to_db
from features.self_healing.sync_vectors import main_async as sync_vectors_async
from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session

# We only import the App and Console from the local hub
from . import (
    console,
    fix_app,
)


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
@core_command(dangerous=True, confirmation=False)
# ID: 9309bc1b-d580-4887-b07d-13eccd137ef7
async def sync_db_registry_command(ctx: typer.Context) -> None:
    """CLI wrapper for the command sync service."""
    from body.cli.admin_cli import app as main_app

    with console.status("[cyan]Syncing CLI commands to database...[/cyan]"):
        # Inject session for proper DI
        async with get_session() as session:
            await _sync_commands_to_db(session, main_app)

    console.print("[green]✅ Database registry sync completed[/green]")


@fix_app.command(
    "vector-sync",
    help="Atomically synchronize vectors between PostgreSQL and Qdrant.",
)
@core_command(dangerous=True, confirmation=True)
# ID: 52bf74e6-e420-474d-9d8e-057d0d1d7023
async def fix_vector_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes to both PostgreSQL and Qdrant (otherwise dry-run).",
    ),
) -> None:
    """
    Atomic bidirectional vector synchronization.
    """
    # Note: dry_run is implicit if write is False
    dry_run = not write

    # We inject the qdrant service from context to reuse the connection
    core_context = ctx.obj

    with console.status("[cyan]Synchronizing vector database...[/cyan]"):
        await sync_vectors_async(
            session=await get_session().__aenter__(),  # Temporary session for internal use
            write=write,
            dry_run=dry_run,
            qdrant_service=core_context.qdrant_service,
        )

    if write:
        console.print("[green]✅ Vector synchronization completed[/green]")
