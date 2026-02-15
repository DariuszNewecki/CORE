# src/features/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.

Enhanced to extract CommandMeta when available, with intelligent fallback.

Phase 1 Addition: audit_cli_registry() for CLI Command Registry Audit
(Roadmap Phase 1, Deliverable #1 — no DB dependency).
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


def _introspect_typer_app(
    app: TyperAppLike,
    prefix: str = "",
    include_missing_handlers: bool = False,
) -> list[dict[str, Any]]:
    """
    Recursively scans a Typer app to discover all commands and their metadata.

    Enhanced to extract CommandMeta when available via @command_meta decorator,
    with intelligent fallback to inference for legacy commands.

    Args:
        app: Typer application to introspect
        prefix: Hierarchical prefix for nested command groups
        include_missing_handlers: If True, include entries for commands with no
            callback (marked with has_callback=False) and add audit-only keys
            (has_callback, has_explicit_meta, experimental) to all entries.
            Default False preserves existing behavior exactly — same dict shape,
            same keys.

    Returns:
        List of command metadata dictionaries ready for database upsert
    """
    commands = []

    for cmd_info in app.registered_commands:
        if not cmd_info.name:
            continue

        callback = cmd_info.callback

        # Full hierarchical name
        full_name = f"{prefix}{cmd_info.name}"

        if not callback:
            logger.warning("Command %s has no callback, skipping", cmd_info.name)
            if include_missing_handlers:
                commands.append(
                    {
                        "name": full_name,
                        "module": None,
                        "entrypoint": None,
                        "summary": None,
                        "category": prefix.replace(".", " ").strip() or "general",
                        "behavior": None,
                        "layer": None,
                        "aliases": [],
                        "dangerous": False,
                        "requires_approval": False,
                        "constitutional_constraints": [],
                        "help_text": None,
                        "has_callback": False,
                        "has_explicit_meta": False,
                        "experimental": False,
                    }
                )
            continue

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
            if include_missing_handlers:
                command_dict["has_callback"] = True
                command_dict["has_explicit_meta"] = True
                command_dict["experimental"] = meta.experimental
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
            if include_missing_handlers:
                command_dict["has_callback"] = True
                command_dict["has_explicit_meta"] = False
                command_dict["experimental"] = False

        commands.append(command_dict)

    # Recursively process command groups
    for group_info in app.registered_groups:
        if group_info.name:
            new_prefix = f"{prefix}{group_info.name}."
            commands.extend(
                _introspect_typer_app(
                    group_info.typer_instance,
                    new_prefix,
                    include_missing_handlers=include_missing_handlers,
                )
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


# =============================================================================
# Phase 1 — CLI Registry Audit (no DB dependency)
# Roadmap: Phase 1, Deliverable #1 (CLI Command Registry Audit)
# =============================================================================


def _detect_duplicate_canonicals(
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Find commands sharing the same canonical name.

    Uses the "name" field — the same key used by _sync_commands_to_db
    for deduplication and as the database primary key.
    """
    canonical_map: dict[str, list[str]] = {}
    for cmd in commands:
        name = cmd.get("name")
        if name:
            # Track the entrypoint to distinguish where duplicates originate
            location = cmd.get("entrypoint") or cmd.get("module") or "(unknown)"
            canonical_map.setdefault(name, []).append(location)

    return [
        {"canonical_name": name, "locations": locations}
        for name, locations in canonical_map.items()
        if len(locations) > 1
    ]


# ID: c818737b-10ca-4e3a-b327-b5e0cd928548
def audit_cli_registry(main_app: TyperAppLike) -> dict[str, Any]:
    """
    Audit the CLI command registry for integrity issues.

    Reuses _introspect_typer_app (with include_missing_handlers=True) for
    discovery, then computes a structured diagnostic report.
    No database dependency — pure introspection.

    Checks performed:
    - Handler presence (callback is not None)
    - @command_meta coverage (explicit vs inferred)
    - Duplicate canonical names (using the "name" field,
      same key _sync_commands_to_db uses as primary key)
    - Experimental command count

    Args:
        main_app: The root Typer application

    Returns:
        JSON-serializable dict with audit findings

    Roadmap: Phase 1, Deliverables #1 and #2
    """
    commands = _introspect_typer_app(main_app, include_missing_handlers=True)

    total = len(commands)
    with_explicit = sum(1 for c in commands if c.get("has_explicit_meta"))
    with_inferred = sum(
        1 for c in commands if c.get("has_callback") and not c.get("has_explicit_meta")
    )
    missing_handlers = [
        {"name": c["name"], "category": c.get("category", "")}
        for c in commands
        if not c.get("has_callback")
    ]
    experimental = [
        {"name": c["name"], "category": c.get("category", "")}
        for c in commands
        if c.get("experimental")
    ]
    duplicates = _detect_duplicate_canonicals(commands)

    issue_count = len(missing_handlers) + len(duplicates)
    meta_coverage_pct = (with_explicit / total * 100) if total > 0 else 0.0

    return {
        "total_commands": total,
        "with_explicit_meta": with_explicit,
        "with_inferred_meta": with_inferred,
        "meta_coverage_pct": round(meta_coverage_pct, 1),
        "missing_handlers": missing_handlers,
        "duplicates": duplicates,
        "experimental": experimental,
        "experimental_count": len(experimental),
        "commands": commands,
        "issue_count": issue_count,
        "is_healthy": issue_count == 0,
    }
