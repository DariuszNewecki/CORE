# src/body/cli/logic/sync.py

"""
Implements the 'knowledge sync' command, the single source of truth for
synchronizing the codebase state (IDs) with the database.
"""

from __future__ import annotations

import typer

from features.introspection.sync_service import run_sync_with_db
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


async def _async_sync_knowledge(write: bool):
    """Core async logic for the sync command."""
    logger.info(
        "🚀 Synchronizing codebase state with database using temp table strategy..."
    )
    if not write:
        logger.warning(
            "💧 Dry Run: This command no longer supports a dry run due to its database-centric logic."
        )
        logger.info("   Run with '--write' to execute the synchronization.")
        return

    # FIXED: Pass session to run_sync_with_db
    async with get_session() as session:
        stats = await run_sync_with_db(session)

    logger.info("--- Knowledge Sync Summary ---")
    logger.info("   Scanned from code:  %s symbols", stats["scanned"])
    logger.info("   New symbols added:  %s", stats["inserted"])
    logger.info("   Existing symbols updated: %s", stats["updated"])
    logger.info("   Obsolete symbols removed: %s", stats["deleted"])
    logger.info("✅ Database is now synchronized with the codebase.")


# ID: 3234fb7f-f5d6-4111-b926-455657955794
async def sync_knowledge_base(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the database."
    ),
):
    """Scans the codebase and syncs all symbols and their IDs to the database."""
    await _async_sync_knowledge(write)
