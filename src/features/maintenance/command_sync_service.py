# src/features/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models import CliCommand
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 10bc5565-2f20-4497-8865-c36de47dcb48
class TyperCommandLike(Protocol):
    name: str | None
    callback: Any
    help: str | None


# ID: d01d9def-d26d-4c50-84f6-4ecc6921c9a1
class TyperGroupLike(Protocol):
    name: str | None
    typer_instance: Any


# ID: f9bd5ff6-605c-4575-b5c6-dc61f23bf964
class TyperAppLike(Protocol):
    registered_commands: list[TyperCommandLike]
    registered_groups: list[TyperGroupLike]


def _introspect_typer_app(app: TyperAppLike, prefix: str = "") -> list[dict[str, Any]]:
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


async def _sync_commands_to_db(session: AsyncSession, main_app: TyperAppLike):
    """
    Introspects the main CLI application, discovers all commands, and upserts them
    into the database, making the database the single source of truth.

    Args:
        session: Database session (injected dependency)
        main_app: The main Typer application to introspect
    """
    logger.info("Synchronizing CLI command registry with the database...")
    discovered_commands = _introspect_typer_app(main_app)

    if not discovered_commands:
        logger.info("No commands discovered. Nothing to sync.")
        return

    logger.info(
        "Discovered %s commands from the application code.", len(discovered_commands)
    )

    async with session.begin():
        await session.execute(delete(CliCommand))
        stmt = pg_insert(CliCommand).values(discovered_commands)
        update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["name"], set_=update_dict
        )
        await session.execute(upsert_stmt)

    logger.info(
        "Successfully synchronized %s commands to the database.",
        len(discovered_commands),
    )
