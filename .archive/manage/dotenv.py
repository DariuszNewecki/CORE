# src/body/cli/commands/manage/dotenv.py

"""Refactored logic for src/body/cli/commands/manage/dotenv.py."""

from __future__ import annotations

import typer

from features.maintenance.dotenv_sync_service import run_dotenv_sync
from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session


dotenv_sub_app = typer.Typer(
    help="Manage runtime configuration from .env.", no_args_is_help=True
)


@dotenv_sub_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: f981e938-c9d6-44a4-8bd4-f54a7e13f158
async def dotenv_sync_command(
    ctx: typer.Context, write: bool = typer.Option(False, "--write")
):
    """Sync settings from .env to the database."""
    async with get_session() as session:
        await run_dotenv_sync(session, dry_run=not write)
