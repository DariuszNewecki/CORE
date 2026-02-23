# src/cli/resources/database/sync_registry.py

import typer

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.models.command_meta import (
    CommandBehavior,
    CommandLayer,
    command_meta,
)  # Add this import

from .hub import app


@app.command("sync-registry")
@command_meta(
    canonical_name="database.sync-registry",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize the live CLI command structure to the database.",
    dangerous=True,  # Explicitly mark as dangerous
)
@core_command(dangerous=True, requires_context=False)
# ID: d71b92d9-d954-48dd-9059-68f0b3ed4442
async def sync_registry_cmd(
    # Add the mandatory write parameter
    write: bool = typer.Option(
        False, "--write", help="Actually persist the registry to the database."
    ),
):
    """
    Synchronize the live CLI command structure (metadata) to the database.
    This makes the DB the Single Source of Truth for available system neurons.
    """
    if not write:
        typer.echo(
            "📋 DRY RUN: Would synchronize CLI Registry to database. Use --write to apply."
        )
        return

    from body.maintenance.command_sync_service import _sync_commands_to_db
    from cli.admin_cli import app as main_app

    async with get_session() as session:
        await _sync_commands_to_db(session, main_app)

    typer.echo("✅ CLI Registry synchronized to database.")
