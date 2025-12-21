# src/features/self_healing/memory_cleanup_service.py
"""
Memory cleanup service - business logic for retention policies.

CONSTITUTIONAL FIX:
- Service layer defines BUSINESS LOGIC (what to clean, when)
- Repository layer handles DATA ACCESS (how to clean)
- Controller layer manages TRANSACTIONS (commit/rollback)

This enforces db.write_via_governed_cli by removing session.commit() from service.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.repositories.memory_repository import MemoryRepository
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cdd06098-1089-41d7-a5e9-8f06570fd189
class MemoryCleanupService:
    """
    Implements retention policies for agent memory.

    ARCHITECTURAL PRINCIPLE:
    - This service contains POLICY (business rules)
    - Repository contains PERSISTENCE (data operations)
    - Caller contains TRANSACTION (commit/rollback)
    """

    def __init__(self, session):
        """
        Initialize with database session.

        Args:
            session: AsyncSession - caller manages transaction boundary
        """
        self.session = session
        self.repository = MemoryRepository(session)

    @atomic_action(
        action_id="cleanup.agent_memory",
        intent="Prune old agent memory entries per retention policy",
        impact=ActionImpact.WRITE_DATA,
        policies=["data_retention", "database_maintenance"],
    )
    # ID: e9fa0b0e-2054-41ab-bd37-277efa5992c6
    async def cleanup_old_memories(
        self,
        days_to_keep_episodes: int = 30,
        days_to_keep_reflections: int = 90,
        dry_run: bool = True,
    ) -> ActionResult:
        """
        Execute memory retention policy.

        IMPORTANT: Does NOT commit. Caller must commit if successful.

        Args:
            days_to_keep_episodes: Retain episodes for this many days
            days_to_keep_reflections: Retain reflections for this many days
            dry_run: If True, only count what would be deleted

        Returns:
            ActionResult with deletion counts
        """
        cutoff_episodes = datetime.utcnow() - timedelta(days=days_to_keep_episodes)
        cutoff_reflections = datetime.utcnow() - timedelta(
            days=days_to_keep_reflections
        )

        try:
            if dry_run:
                # Dry run: just count
                episodes_count = await self.repository.count_episodes_older_than(
                    cutoff_episodes
                )
                reflections_count = await self.repository.count_reflections_older_than(
                    cutoff_reflections
                )
                decisions_count = 0  # Would be cascade deleted

                logger.info(
                    "Memory cleanup DRY RUN: would delete %d episodes, %d reflections",
                    episodes_count,
                    reflections_count,
                )
            else:
                # Real run: execute deletes (but don't commit)
                episodes_count = await self.repository.delete_old_episodes(
                    cutoff_episodes
                )
                reflections_count = await self.repository.delete_old_reflections(
                    cutoff_reflections
                )
                decisions_count = 0  # Cascade counted in episodes

                logger.info(
                    "Memory cleanup EXECUTED: deleted %d episodes, %d reflections (awaiting commit)",
                    episodes_count,
                    reflections_count,
                )

            return ActionResult(
                ok=True,
                data={
                    "episodes_deleted": episodes_count,
                    "decisions_deleted": decisions_count,
                    "reflections_deleted": reflections_count,
                    "dry_run": dry_run,
                    "retention_policy": {
                        "episodes_days": days_to_keep_episodes,
                        "reflections_days": days_to_keep_reflections,
                    },
                },
            )

        except Exception as e:
            logger.error("Memory cleanup failed: %s", e)
            # Don't commit on error - caller will rollback
            return ActionResult(ok=False, data={"error": str(e)})
