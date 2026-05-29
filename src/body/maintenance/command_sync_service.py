# src/body/maintenance/command_sync_service.py

"""
Provides a service to introspect the live Typer CLI application and synchronize
the discovered commands with the `core.cli_commands` database table.

CONSTITUTIONAL HARDENING (v2.4):
- The audit-time ``audit_cli_registry`` entry point was retired (#483) once
  ``cli_gate`` became the autonomous enforcement engine for the eight CLI
  rules; ``self_check_cmd`` now drives those rules through ``cli_gate``
  directly. This module's responsibility narrows to runtime DB sync.
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
