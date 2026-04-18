# src/cli/resources/database/sync_env.py
"""
Environment settings sync command.

Reads variables from .env and upserts them into core.runtime_settings.
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("sync-env")
@command_meta(
    canonical_name="database.sync_env",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Sync .env variables into core.runtime_settings table.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 44ffa6cb-5c9e-4c12-b8ab-ab673dbdf0d4
async def sync_env(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply sync (default: dry-run)"),
) -> None:
    """
    Sync environment variables into the database runtime_settings table.

    Reads variables declared in mind.config.runtime_requirements and upserts
    their current values from .env into core.runtime_settings.

    Constitutional Compliance:
    - Requires --write flag for safety
    - Secret keys are masked in dry-run output

    Examples:
        # Dry-run: show what would be synced
        core-admin database sync-env

        # Apply sync
        core-admin database sync-env --write
    """
    from body.maintenance.dotenv_sync_service import run_dotenv_sync

    logger.info("[bold cyan]⚙️  Environment Settings Sync[/bold cyan]")
    logger.info("Mode: %s", "WRITE" if write else "DRY-RUN")
    console.print()
    try:
        core_context = ctx.obj
        async with get_session() as session:
            await run_dotenv_sync(
                context=core_context, session=session, dry_run=not write
            )
        if not write:
            logger.info()
            logger.info("[yellow]💡 Run with --write to apply sync[/yellow]")
        else:
            logger.info("[green]✅ Environment settings synced to database[/green]")
    except Exception as e:
        logger.error("Environment sync failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
