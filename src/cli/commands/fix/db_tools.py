# src/cli/commands/fix/db_tools.py
"""
Database and vector-related commands for the 'fix' CLI group.

Refactored to use the Constitutional CLI Framework (@core_command).
CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Synchronizes local CLI structure and vectors with the Mind (DB/Qdrant).
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer

from body.maintenance.command_sync_service import _sync_commands_to_db
from body.maintenance.sync_vectors import main_async as sync_vectors_async
from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session

from . import fix_app


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
@core_command(dangerous=True, confirmation=False)
# ID: 40bd8310-f78e-43bd-bc79-21b3519bc802
async def sync_db_registry_command(ctx: typer.Context) -> None:
    """CLI wrapper for the command sync service."""
    from cli.admin_cli import app as main_app

    with logger.info("[cyan]Syncing CLI commands to database...[/cyan]"):
        async with get_session() as session:
            await _sync_commands_to_db(session, main_app)
    logger.info("[green]✅ Database registry sync completed[/green]")


@fix_app.command(
    "vector-sync", help="Atomically synchronize vectors between PostgreSQL and Qdrant."
)
@core_command(dangerous=True, confirmation=True)
# ID: 945cd068-91ec-4e32-acd0-2e1be5148732
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
    dry_run = not write
    core_context = ctx.obj
    with logger.info("[cyan]Synchronizing vector database...[/cyan]"):
        await sync_vectors_async(
            session=await get_session().__aenter__(),
            write=write,
            dry_run=dry_run,
            qdrant_service=core_context.qdrant_service,
        )
    if write:
        logger.info("[green]✅ Vector synchronization completed[/green]")
