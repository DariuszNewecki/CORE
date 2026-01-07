# src/features/self_healing/memory_cleanup_service.py
"""
Memory cleanup service - business logic for retention policies.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from shared.action_types import ActionImpact, ActionResult
from shared.infrastructure.repositories.memory_repository import MemoryRepository
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cdd06098-1089-41d7-a5e9-8f06570fd189
class MemoryCleanupService:
    """
    Implements retention policies for agent memory.
    """

    def __init__(self, session):
        self.session = session
        self.repository = MemoryRepository(session)

    # ID: e9fa0b0e-2054-41ab-bd37-277efa5992c6
    async def cleanup_old_memories(
        self,
        days_to_keep_episodes: int = 30,
        days_to_keep_reflections: int = 90,
        dry_run: bool = True,
    ) -> ActionResult:
        """
        Execute memory retention policy.
        """
        cutoff_episodes = datetime.utcnow() - timedelta(days=days_to_keep_episodes)
        cutoff_reflections = datetime.utcnow() - timedelta(
            days=days_to_keep_reflections
        )

        try:
            if dry_run:
                episodes_count = await self.repository.count_episodes_older_than(
                    cutoff_episodes
                )
                reflections_count = await self.repository.count_reflections_older_than(
                    cutoff_reflections
                )
                decisions_count = 0
            else:
                episodes_count = await self.repository.delete_old_episodes(
                    cutoff_episodes
                )
                reflections_count = await self.repository.delete_old_reflections(
                    cutoff_reflections
                )
                decisions_count = 0

            return ActionResult(
                action_id="cleanup.agent_memory",
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
                impact=ActionImpact.WRITE_DATA,
            )

        except Exception as e:
            logger.error("Memory cleanup failed: %s", e)
            return ActionResult(
                action_id="cleanup.agent_memory", ok=False, data={"error": str(e)}
            )
