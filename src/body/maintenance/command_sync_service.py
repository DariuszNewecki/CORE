# src/body/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.

CONSTITUTIONAL HARDENING (v2.3):
- Decoupled from hardcoded design rules.
- Receives constitutional parameters from the Will (CLI) layer.
- Enforces cli.dangerous_explicit and cli.help_required.
"""

from __future__ import annotations

import inspect
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
    Includes physical file paths for constitutional auditing.
    """
    commands: list[dict[str, Any]] = []

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
                        "file_path": None,
                        "summary": None,
                        "category": prefix.replace(".", " ").strip() or "general",
                        "behavior": None,
                        "layer": None,
                        "aliases": [],
                        "dangerous": False,
                        "params_list": [],
                        "has_callback": False,
                        "has_explicit_meta": False,
                    }
                )
            continue

        # Find the physical file where this command is defined
        try:
            file_path: str | None = inspect.getfile(callback)
        except Exception:
            file_path = "unknown"

        # Extract function parameters to check for 'write' flag
        sig = inspect.signature(callback)
        params_list = list(sig.parameters.keys())

        meta = get_command_meta(callback)

        if meta:
            command_dict: dict[str, Any] = {
                "name": meta.canonical_name,
                "module": meta.module or callback.__module__,
                "entrypoint": meta.entrypoint or callback.__name__,
                "file_path": file_path,
                "summary": meta.summary,
                "category": meta.category
                or prefix.replace(".", " ").strip()
                or "general",
                "behavior": meta.behavior.value,
                "layer": meta.layer.value,
                "aliases": meta.aliases or [],
                "dangerous": meta.dangerous,
                "params_list": params_list,
                "has_callback": True,
                "has_explicit_meta": True,
            }
        else:
            inferred = infer_metadata_from_function(
                func=callback, command_name=cmd_info.name, group_prefix=prefix
            )
            command_dict = {
                "name": inferred.canonical_name,
                "module": inferred.module or callback.__module__,
                "entrypoint": inferred.entrypoint or callback.__name__,
                "file_path": file_path,
                "summary": inferred.summary or (cmd_info.help or "").split("\n")[0],
                "category": inferred.category
                or prefix.replace(".", " ").strip()
                or "general",
                "behavior": inferred.behavior.value,
                "layer": inferred.layer.value,
                "aliases": inferred.aliases or [],
                "dangerous": inferred.dangerous,
                "params_list": params_list,
                "has_callback": True,
                "has_explicit_meta": False,
            }

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

    seen_names: set[str] = set()
    deduplicated: list[dict[str, Any]] = []

    for cmd in discovered_commands:
        # DB schema doesn't need audit-only fields, strip them before DB write
        db_ready_cmd = {
            k: v
            for k, v in cmd.items()
            if k
            not in {"params_list", "has_callback", "has_explicit_meta", "file_path"}
        }

        name = db_ready_cmd["name"]
        if name not in seen_names:
            seen_names.add(name)
            deduplicated.append(db_ready_cmd)

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
def audit_cli_registry(
    main_app: TyperAppLike,
    allowed_verbs: set[str] | None = None,
    forbidden_resources: set[str] | None = None,
) -> dict[str, Any]:
    """
    Audit the CLI command registry using provided parameters from the Constitution.
    BODY LAYER: Pure execution, no decision-making.
    """
    commands = _introspect_typer_app(main_app, include_missing_handlers=True)
    violations: list[dict[str, Any]] = []

    # Use provided parameters (The "Law" passed as data)
    verbs = allowed_verbs or set()
    forbidden = forbidden_resources or set()

    for c in commands:
        name_parts = c["name"].split(".")
        resource = name_parts[0]
        action = name_parts[1] if len(name_parts) > 1 else None

        # 1. Rule: cli.no_layer_exposure
        if resource in forbidden:
            violations.append(
                {
                    "rule": "cli.no_layer_exposure",
                    "message": f"Resource '{resource}' exposes internal architecture.",
                    "item": c["name"],
                }
            )

        # 2. Rule: cli.standard_verbs
        if action and verbs and action not in verbs:
            violations.append(
                {
                    "rule": "cli.standard_verbs",
                    "message": f"Action '{action}' is non-standard.",
                    "item": c["name"],
                }
            )

        # 3. Rule: cli.help_required
        if not c.get("summary"):
            violations.append(
                {
                    "rule": "cli.help_required",
                    "message": "Command is missing a help summary (docstring).",
                    "item": c["name"],
                }
            )

        # 4. Rule: cli.dangerous_explicit
        # If behavior is 'mutate', it MUST be marked 'dangerous' and have a 'write' param
        if c.get("behavior") == "mutate":
            if not c.get("dangerous"):
                violations.append(
                    {
                        "rule": "cli.dangerous_explicit",
                        "message": "Mutating command is not marked 'dangerous=True' in metadata.",
                        "item": c["name"],
                    }
                )
            if "write" not in c.get("params_list", []):
                violations.append(
                    {
                        "rule": "cli.dangerous_explicit",
                        "message": "Mutating command is missing mandatory 'write' parameter.",
                        "item": c["name"],
                    }
                )

    # Calculate statistics
    total = len(commands)
    with_explicit = sum(1 for c in commands if c.get("has_explicit_meta"))
    missing_handlers = [c for c in commands if not c.get("has_callback")]

    # Duplicate Detection (by canonical name)
    canonical_map: dict[str, list[str]] = {}
    for cmd in commands:
        name = cmd.get("name")
        if name:
            canonical_map.setdefault(name, []).append(cmd.get("entrypoint", "unknown"))

    duplicates = [
        {"canonical_name": k, "locations": v}
        for k, v in canonical_map.items()
        if len(v) > 1
    ]

    issue_count = len(missing_handlers) + len(duplicates) + len(violations)

    return {
        "is_healthy": issue_count == 0,
        "issue_count": issue_count,
        "violations": violations,
        "total_commands": total,
        "with_explicit_meta": with_explicit,
        "missing_handlers": missing_handlers,
        "duplicates": duplicates,
        "commands": commands,
    }
