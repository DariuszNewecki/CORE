# src/cli/resources/database/sync_env.py
"""
Environment settings sync command.

Reads variables from .env and upserts them into core.runtime_settings.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
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
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
async def sync_env(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply sync (default: dry-run)",
    ),
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

    console.print("[bold cyan]⚙️  Environment Settings Sync[/bold cyan]")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    console.print()

    try:
        core_context = ctx.obj

        async with get_session() as session:
            await run_dotenv_sync(
                context=core_context,
                session=session,
                dry_run=not write,
            )

        if not write:
            console.print()
            console.print("[yellow]💡 Run with --write to apply sync[/yellow]")
        else:
            console.print("[green]✅ Environment settings synced to database[/green]")

    except Exception as e:
        logger.error("Environment sync failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
