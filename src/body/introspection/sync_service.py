# src/features/introspection/sync_service.py

"""
Symbol Synchronization Service
Orchestrates Mind/Body alignment via modularized components.
"""

from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncSession

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger

from .sync.engine import run_db_merge
from .sync.scanner import SymbolScanner


logger = getLogger(__name__)


@atomic_action(
    action_id="sync.knowledge_graph",
    intent="Synchronize filesystem symbols to the persistent database Knowledge Graph",
    impact=ActionImpact.WRITE_DATA,
    policies=["knowledge.database_ssot", "db.write_via_governed_cli"],
    category="introspection",
)
# ID: 3d99a5e7-06f8-4cfa-aba8-41a6e0655987
async def run_sync_with_db(session: AsyncSession) -> ActionResult:
    """Entry point for the database-centric sync logic."""
    start_time = time.time()
    logger.info("🚀 Starting symbol sync with database (Mind/Body alignment)")

    # 1. Scan the Body
    from shared.infrastructure.bootstrap_registry import bootstrap_registry

    scanner = SymbolScanner(repo_root=bootstrap_registry.get_repo_path())
    code_state = scanner.scan()

    # 2. Update the Mind
    stats = await run_db_merge(session, code_state)
    await session.commit()

    logger.info(
        "✅ Sync complete. Scanned: %d, New: %d, Updated: %d, Delta: %d",
        stats["scanned"],
        stats["inserted"],
        stats["updated"],
        stats["deleted"],
    )

    return ActionResult(
        action_id="sync.knowledge_graph",
        ok=True,
        data=stats,
        duration_sec=time.time() - start_time,
        impact=ActionImpact.WRITE_DATA,
    )
