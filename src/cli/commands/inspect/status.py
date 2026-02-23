# src/body/cli/commands/inspect/status.py
# ID: 6e2713f9-3ab6-48fb-825d-71aa034352aa

"""
System and database status inspection commands.
"""

from __future__ import annotations

import typer
from rich.console import Console

import cli.logic.status as status_logic
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


console = Console()


@command_meta(
    canonical_name="inspect.status",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Display database connection and migration status",
)
@core_command(dangerous=False, requires_context=False)
# ID: 33e945f6-45aa-42e5-a008-c5fad806b92e
async def status_command(ctx: typer.Context) -> None:
    """Display database connection and migration status."""
    report = await status_logic._get_status_report()

    if report.is_connected:
        console.print("Database connection: OK")
    else:
        console.print("Database connection: FAILED")

    if report.db_version:
        console.print(f"Database version: {report.db_version}")
    else:
        console.print("Database version: none")

    pending = list(report.pending_migrations)
    if not pending:
        console.print("Migrations are up to date.")
    else:
        console.print(f"Found {len(pending)} pending migrations")
        for mig in sorted(pending):
            console.print(f"- {mig}")


# Export commands for registration
status_commands = [
    {"name": "status", "func": status_command},
]
