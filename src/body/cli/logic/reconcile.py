# src/body/cli/logic/reconcile.py
"""
Implements the 'knowledge reconcile-from-cli' command to link declared
capabilities to their implementations in the database using the CLI registry as the map.
"""

from __future__ import annotations

import asyncio

import typer
import yaml
from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
CLI_REGISTRY_PATH = (
    settings.REPO_PATH / ".intent" / "mind" / "knowledge" / "cli_registry.yaml"
)


async def _async_reconcile():
    """
    Reads the CLI registry and updates the 'key' in the symbols table for all
    symbols that implement a registered command.
    """
    logger.info("Reconciling capabilities from CLI registry to database...")

    if not CLI_REGISTRY_PATH.exists():
        logger.error("CLI Registry not found at %s", CLI_REGISTRY_PATH)
        raise typer.Exit(code=1)

    registry = yaml.safe_load(CLI_REGISTRY_PATH.read_text("utf-8"))
    commands = registry.get("commands", [])

    updates_to_perform = []
    for command in commands:
        entrypoint = command.get("entrypoint")
        capabilities = command.get("implements", [])
        if not entrypoint or not capabilities:
            continue

        module_path, function_name = entrypoint.split("::")
        file_path_str = "src/" + module_path.replace(".", "/") + ".py"
        symbol_path = f"{file_path_str}::{function_name}"
        primary_key = capabilities[0]

        updates_to_perform.append(
            {
                "key": primary_key,
                "symbol_path": symbol_path,
            }
        )

    if not updates_to_perform:
        logger.warning("No capabilities with entrypoints found in CLI registry.")
        return

    logger.info(f"Found {len(updates_to_perform)} capability implementations to link.")

    linked_count = 0
    async with get_session() as session:
        async with session.begin():
            for update in updates_to_perform:
                stmt = text(
                    """
                    UPDATE core.symbols SET key = :key, updated_at = NOW()
                    WHERE symbol_path = :symbol_path AND key IS NULL;
                    """
                )
                result = await session.execute(stmt, update)
                if result.rowcount > 0:
                    linked_count += 1

    logger.info("Successfully linked %s capabilities.", linked_count)


# ID: b43fc6d4-413b-47f2-8a0c-7860836913ab
def reconcile_from_cli():
    """Typer-compatible wrapper for the async reconcile logic."""
    asyncio.run(_async_reconcile())
