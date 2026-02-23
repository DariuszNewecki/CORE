# src/body/cli/logic/sync.py
# ID: 3234fb7f-f5d6-4111-b926-455657955794
"""
Headless logic for synchronizing the codebase state with the database.
Complies with body_contracts.json (no UI imports).
"""

from __future__ import annotations

from body.introspection.sync_service import run_sync_with_db
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 26a3ed07-80bb-4a78-a05d-862cae7968e3
async def sync_knowledge_base(write: bool = False) -> dict:
    """
    Scans the codebase and syncs all symbols and their IDs to the database.

    Returns:
        dict: Sync statistics.
    """
    logger.info("🚀 Synchronizing codebase state with database...")

    if not write:
        logger.info("DRY-RUN: Knowledge sync requires write=True to persist changes.")
        return {
            "status": "dry_run",
            "scanned": 0,
            "inserted": 0,
            "updated": 0,
            "deleted": 0,
        }

    async with get_session() as session:
        # run_sync_with_db returns an ActionResult; we extract the data for the caller
        result = await run_sync_with_db(session)
        stats = result.data

    logger.info("--- Knowledge Sync Summary ---")
    logger.info("   Scanned from code:  %s symbols", stats.get("scanned", 0))
    logger.info("   New symbols added:  %s", stats.get("inserted", 0))
    logger.info("   Existing symbols updated: %s", stats.get("updated", 0))
    logger.info("   Obsolete symbols removed: %s", stats.get("deleted", 0))

    return stats
