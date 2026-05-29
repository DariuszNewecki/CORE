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

from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cli.app_introspection import walk_typer_app
from shared.infrastructure.database.models import CliCommand
from shared.logger import getLogger
from shared.protocols.typer_protocols import (
    TyperAppLike,
)


logger = getLogger(__name__)


def _introspect_typer_app(
    app: TyperAppLike,
    prefix: str = "",
    include_missing_handlers: bool = False,
) -> list[dict[str, Any]]:
    """Back-compat shim. New code should import ``walk_typer_app`` from
    ``shared.cli.app_introspection`` directly. Strips the ``callback``
    field that the shared walker now exposes, so legacy callers
    (audit_cli_registry, _sync_commands_to_db downstream consumers) see
    the same dict shape as before."""
    return [
        {k: v for k, v in cmd.items() if k != "callback"}
        for cmd in walk_typer_app(
            app, prefix=prefix, include_missing_handlers=include_missing_handlers
        )
    ]


async def _sync_commands_to_db(session: AsyncSession, main_app: TyperAppLike):
    """
    Introspects the main CLI application and syncs to database.
    """
    discovered_commands = walk_typer_app(main_app)

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
            not in {
                "params_list",
                "has_callback",
                "has_explicit_meta",
                "file_path",
                "callback",
            }
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
                        "message": "Mutating command is not marked as dangerous.",
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
