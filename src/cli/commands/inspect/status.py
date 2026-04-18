# src/cli/commands/inspect/status.py
"""
System and database status inspection commands.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

import cli.logic.status as status_logic
from cli.utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


console = Console()


@command_meta(
    canonical_name="inspect.status",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Display database connection and migration status",
)
@core_command(dangerous=False, requires_context=False)
# ID: 4d56d191-4d50-41f6-8d64-cc5732a92186
async def status_command(ctx: typer.Context) -> None:
    """Display database connection and migration status."""
    report = await status_logic._get_status_report()
    if report.is_connected:
        logger.info("Database connection: OK")
    else:
        logger.info("Database connection: FAILED")
    if report.db_version:
        logger.info("Database version: %s", report.db_version)
    else:
        logger.info("Database version: none")
    pending = list(report.pending_migrations)
    if not pending:
        logger.info("Migrations are up to date.")
    else:
        logger.info("Found %s pending migrations", len(pending))
        for mig in sorted(pending):
            logger.info("- %s", mig)


status_commands = [{"name": "status", "func": status_command}]
