# src/body/cli/logic/reconcile.py

"""
Implements the 'knowledge reconcile-from-cli' command to link declared
capabilities to their implementations in the database, using the DB-backed
CLI registry (core.cli_commands) as the authoritative map.

Legacy YAML registry files are deprecated and must not be referenced here.
"""

from __future__ import annotations

from sqlalchemy import text

from shared.infrastructure.repositories.db.engine import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


def _entrypoint_to_symbol_path(entrypoint: str) -> str | None:
    """
    Converts 'package.module::function' into 'src/package/module.py::function'.

    Returns None for invalid entrypoints.
    """
    if "::" not in entrypoint:
        return None
    module_path, function_name = entrypoint.split("::", 1)
    module_path = (module_path or "").strip()
    function_name = (function_name or "").strip()
    if not module_path or not function_name:
        return None
    file_path_str = "src/" + module_path.replace(".", "/") + ".py"
    return f"{file_path_str}::{function_name}"


async def _async_reconcile() -> None:
    """
    Reads DB CLI registry and updates 'core.symbols.key' for symbols that
    implement registered commands (only when key is currently NULL).
    """
    logger.info("Reconciling capabilities from DB CLI registry to symbols table...")

    fetch_stmt = text(
        """
        SELECT
            name,
            entrypoint,
            implements
        FROM core.cli_commands
        WHERE entrypoint IS NOT NULL
        """
    )

    updates: list[dict[str, str]] = []

    async with get_session() as session:
        result = await session.execute(fetch_stmt)
        rows = result.mappings().all()

    if not rows:
        logger.warning("No CLI commands found in DB registry (core.cli_commands).")
        return

    for row in rows:
        entrypoint = row.get("entrypoint")
        implements = row.get(
            "implements"
        )  # may be TEXT, JSON, JSONB, or NULL depending on schema
        if not entrypoint:
            continue

        symbol_path = _entrypoint_to_symbol_path(entrypoint)
        if not symbol_path:
            continue

        # Implements handling:
        # - If implements is a list/array -> take first element
        # - If implements is a string -> treat as single capability
        # - Otherwise -> skip
        capability_key: str | None = None
        if isinstance(implements, list) and implements:
            first = implements[0]
            capability_key = first if isinstance(first, str) and first.strip() else None
        elif isinstance(implements, str) and implements.strip():
            capability_key = implements.strip()

        if not capability_key:
            continue

        updates.append({"key": capability_key, "symbol_path": symbol_path})

    if not updates:
        logger.warning(
            "No reconcile candidates found (missing implements/entrypoints)."
        )
        return

    logger.info("Found %s capability implementations to link.", len(updates))

    update_stmt = text(
        """
        UPDATE core.symbols
        SET key = :key,
            updated_at = NOW()
        WHERE symbol_path = :symbol_path
          AND key IS NULL
        """
    )

    linked_count = 0
    async with get_session() as session:
        async with session.begin():
            for u in updates:
                res = await session.execute(update_stmt, u)
                if res.rowcount and res.rowcount > 0:
                    linked_count += int(res.rowcount)

    logger.info("Successfully linked %s capability mappings.", linked_count)


# ID: 0bb0702a-9b3b-487a-8049-a1fe9ad7cf41
async def reconcile_from_cli() -> None:
    """Typer-compatible async entrypoint."""
    await _async_reconcile()
