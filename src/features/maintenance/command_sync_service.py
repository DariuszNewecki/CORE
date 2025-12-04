# src/features/maintenance/command_sync_service.py
"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from services.database.models import CliCommand
from services.database.session_manager import get_session
from shared.logger import getLogger
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = getLogger(__name__)

console = Console()


def _introspect_typer_app(app: typer.Typer, prefix: str = "") -> list[dict[str, Any]]:
    """Recursively scans a Typer app to discover all commands and their metadata."""
    commands = []

    for cmd_info in app.registered_commands:
        if not cmd_info.name:
            continue

        full_name = f"{prefix}{cmd_info.name}"
        callback = cmd_info.callback
        module_name = callback.__module__ if callback else "unknown"

        commands.append(
            {
                "name": full_name,
                "module": module_name,
                "entrypoint": callback.__name__ if callback else "unknown",
                "summary": (cmd_info.help or "").split("\n")[0],
                "category": prefix.replace(".", " ").strip() or "general",
            }
        )

    for group_info in app.registered_groups:
        if group_info.name:
            new_prefix = f"{prefix}{group_info.name}."
            commands.extend(
                _introspect_typer_app(group_info.typer_instance, new_prefix)
            )

    return commands


async def _sync_commands_to_db(main_app: typer.Typer):
    """
    Introspects the main CLI application, discovers all commands, and upserts them
    into the database, making the database the single source of truth.
    """
    logger.info(
        "[bold cyan]🚀 Synchronizing CLI command registry with the database...[/bold cyan]"
    )

    discovered_commands = _introspect_typer_app(main_app)

    if not discovered_commands:
        logger.info(
            "[bold yellow]⚠️ No commands discovered. Nothing to sync.[/bold yellow]"
        )
        return

    logger.info(
        f"   -> Discovered {len(discovered_commands)} commands from the application code."
    )

    async with get_session() as session:
        async with session.begin():
            # Clear the table to ensure a clean sync from the code's source of truth
            await session.execute(delete(CliCommand))

            # Use PostgreSQL's ON CONFLICT DO UPDATE for an upsert operation
            stmt = pg_insert(CliCommand).values(discovered_commands)
            update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["name"],
                set_=update_dict,
            )

            await session.execute(upsert_stmt)

    logger.info(
        f"[bold green]✅ Successfully synchronized {len(discovered_commands)} commands to the database.[/bold green]"
    )
