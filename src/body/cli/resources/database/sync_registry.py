# src/body/cli/resources/database/sync_registry.py

import typer

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


@app.command("sync-registry")
@core_command(dangerous=True, requires_context=False)
# ID: d71b92d9-d954-48dd-9059-68f0b3ed4442
async def sync_registry_cmd():
    """
    Synchronize the live CLI command structure (metadata) to the database.
    This makes the DB the Single Source of Truth for available system neurons.
    """
    from body.cli.admin_cli import app as main_app
    from body.maintenance.command_sync_service import _sync_commands_to_db

    async with get_session() as session:
        await _sync_commands_to_db(session, main_app)

    typer.echo("✅ CLI Registry synchronized to database.")
