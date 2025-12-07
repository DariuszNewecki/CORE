# src/body/cli/logic/sync.py
"""
Implements the 'knowledge sync' command, the single source of truth for
synchronizing the codebase state (IDs) with the database.
"""

from __future__ import annotations

import asyncio

import typer
from features.introspection.sync_service import run_sync_with_db
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

    stats = await run_sync_with_db()

    logger.info("--- Knowledge Sync Summary ---")
    logger.info(f"   Scanned from code:  {stats['scanned']} symbols")
    logger.info(f"   New symbols added:  {stats['inserted']}")
    logger.info(f"   Existing symbols updated: {stats['updated']}")
    logger.info(f"   Obsolete symbols removed: {stats['deleted']}")
    logger.info("✅ Database is now synchronized with the codebase.")


# ID: 89517800-0799-476e-8078-a184519a76a1
def sync_knowledge_base(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the database."
    ),
):
    """Scans the codebase and syncs all symbols and their IDs to the database."""
    asyncio.run(_async_sync_knowledge(write))
