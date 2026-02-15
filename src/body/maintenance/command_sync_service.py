# src/body/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.

MOVED: From features/maintenance to body/maintenance (Constitutional Rebirth Wave 1).
FIXED: Restored missing report keys for the Admin Self-Check UI.
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
    """
    commands = []

    for cmd_info in app.registered_commands:
        if not cmd_info.name:
            continue

        callback = cmd_info.callback
        full_name = f"{prefix}{cmd_info.name}"

        if not callback:
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

        meta = get_command_meta(callback)

        if meta:
            command_dict = {
                "name": meta.canonical_name,
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
            inferred = infer_metadata_from_function(
                func=callback, command_name=cmd_info.name, group_prefix=prefix
            )
            command_dict = {
                "name": inferred.canonical_name,
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
    Introspects the main CLI application and syncs to database.
    """
    discovered_commands = _introspect_typer_app(main_app)

    if not discovered_commands:
        return

    seen_names = set()
    deduplicated = []

    for cmd in discovered_commands:
        name = cmd["name"]
        if name not in seen_names:
            seen_names.add(name)
            deduplicated.append(cmd)

    async with session.begin():
        await session.execute(delete(CliCommand))
        if deduplicated:
            stmt = pg_insert(CliCommand).values(deduplicated)
            update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["name"], set_=update_dict
            )
            await session.execute(upsert_stmt)


# ID: c818737b-10ca-4e3a-b327-b5e0cd928548
def audit_cli_registry(main_app: TyperAppLike) -> dict[str, Any]:
    """
    Audit the CLI command registry for integrity issues.
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

    # Simple duplicate detection
    canonical_map = {}
    for cmd in commands:
        name = cmd.get("name")
        if name:
            canonical_map.setdefault(name, []).append(cmd.get("entrypoint", "unknown"))

    duplicates = [
        {"canonical_name": k, "locations": v}
        for k, v in canonical_map.items()
        if len(v) > 1
    ]
    issue_count = len(missing_handlers) + len(duplicates)

    return {
        "total_commands": total,
        "with_explicit_meta": with_explicit,
        "with_inferred_meta": with_inferred,
        "meta_coverage_pct": (
            round((with_explicit / total * 100), 1) if total > 0 else 0.0
        ),
        "missing_handlers": missing_handlers,
        "duplicates": duplicates,
        "experimental": experimental,
        "experimental_count": len(experimental),
        "issue_count": issue_count,
        "is_healthy": issue_count == 0,
        "commands": commands,
    }
