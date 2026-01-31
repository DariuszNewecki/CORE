# src/features/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.

Enhanced to extract CommandMeta when available, with intelligent fallback.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models import CliCommand
from shared.logger import getLogger
from shared.models.command_meta import get_command_meta, infer_metadata_from_function


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
    """
    Recursively scans a Typer app to discover all commands and their metadata.

    Enhanced to extract CommandMeta when available via @command_meta decorator,
    with intelligent fallback to inference for legacy commands.

    Args:
        app: Typer application to introspect
        prefix: Hierarchical prefix for nested command groups

    Returns:
        List of command metadata dictionaries ready for database upsert
    """
    commands = []

    for cmd_info in app.registered_commands:
        if not cmd_info.name:
            continue

        callback = cmd_info.callback
        if not callback:
            logger.warning("Command %s has no callback, skipping", cmd_info.name)
            continue

        # Full hierarchical name
        full_name = f"{prefix}{cmd_info.name}"

        # Try to get explicit CommandMeta from @command_meta decorator
        meta = get_command_meta(callback)

        if meta:
            # Command has explicit metadata - use it
            logger.debug("Found @command_meta for %s", full_name)
            command_dict = {
                "name": meta.canonical_name,  # Use canonical_name as primary key
                "module": meta.module or callback.__module__,
                "entrypoint": meta.entrypoint or callback.__name__,
                "summary": meta.summary,
                "category": meta.category
                or prefix.replace(".", " ").strip()
                or "general",
                "behavior": meta.behavior.value,
                "layer": meta.layer.value,
                "aliases": meta.aliases or [],
                "dangerous": meta.dangerous,
                "requires_approval": meta.requires_approval,
                "constitutional_constraints": meta.constitutional_constraints or [],
                "help_text": meta.help_text,
            }
        else:
            # No explicit metadata - infer from function
            logger.debug("Inferring metadata for %s (no @command_meta)", full_name)
            inferred = infer_metadata_from_function(
                func=callback, command_name=cmd_info.name, group_prefix=prefix
            )
            command_dict = {
                "name": inferred.canonical_name,  # Use canonical_name as primary key
                "module": inferred.module or callback.__module__,
                "entrypoint": inferred.entrypoint or callback.__name__,
                "summary": inferred.summary or (cmd_info.help or "").split("\n")[0],
                "category": inferred.category
                or prefix.replace(".", " ").strip()
                or "general",
                "behavior": inferred.behavior.value,
                "layer": inferred.layer.value,
                "aliases": inferred.aliases or [],
                "dangerous": inferred.dangerous,
                "requires_approval": inferred.requires_approval,
                "constitutional_constraints": inferred.constitutional_constraints or [],
                "help_text": inferred.help_text,
            }

        commands.append(command_dict)

    # Recursively process command groups
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

    # CRITICAL: Deduplicate by canonical name (primary key)
    # Some commands may share the same canonical_name (e.g., aliases)
    seen_names = set()
    deduplicated = []
    duplicates = []

    for cmd in discovered_commands:
        name = cmd["name"]
        if name in seen_names:
            duplicates.append(name)
            logger.warning(
                "Duplicate command name detected: %s (skipping duplicate)", name
            )
        else:
            seen_names.add(name)
            deduplicated.append(cmd)

    if duplicates:
        logger.warning(
            "Found %d duplicate command names: %s",
            len(duplicates),
            ", ".join(set(duplicates)),
        )

    logger.info(
        "Discovered %s commands from the application code.", len(discovered_commands)
    )
    logger.info("After deduplication: %s unique commands.", len(deduplicated))

    # Log sample of what we found
    commands_with_meta = sum(1 for cmd in deduplicated if cmd.get("behavior"))
    logger.info(
        "Commands with @command_meta: %s/%s", commands_with_meta, len(deduplicated)
    )

    async with session.begin():
        # Clear existing and upsert new
        await session.execute(delete(CliCommand))

        if deduplicated:
            stmt = pg_insert(CliCommand).values(deduplicated)
            update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["name"], set_=update_dict
            )
            await session.execute(upsert_stmt)

    logger.info(
        "Successfully synchronized %s commands to the database.",
        len(deduplicated),
    )
