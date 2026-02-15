# src/features/self_healing/memory_cleanup_service.py
# ID: cdd06098-1089-41d7-a5e9-8f06570fd189

"""
Memory cleanup service - business logic for retention policies.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.repositories.memory_repository import MemoryRepository
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f81e034c-23d7-44d5-b7df-58c5a14e06e0
class MemoryCleanupService:
    """
    Implements retention policies for agent memory and action ledgers.
    """

    def __init__(self, session):
        self.session = session
        self.repository = MemoryRepository(session)

    @atomic_action(
        action_id="cleanup.agent_memory",
        intent="Execute memory retention policy",
        impact=ActionImpact.WRITE_DATA,
        policies=["atomic_actions"],
    )
    # ID: e9fa0b0e-2054-41ab-bd37-277efa5992c6
    async def cleanup_old_memories(
        self,
        days_to_keep_episodes: int = 30,
        days_to_keep_reflections: int = 90,
        dry_run: bool = True,
    ) -> ActionResult:
        """
        Execute agent memory retention policy.
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
            else:
                episodes_count = await self.repository.delete_old_episodes(
                    cutoff_episodes
                )
                reflections_count = await self.repository.delete_old_reflections(
                    cutoff_reflections
                )

            return ActionResult(
                action_id="cleanup.agent_memory",
                ok=True,
                data={
                    "episodes_deleted": episodes_count,
                    "reflections_deleted": reflections_count,
                    "dry_run": dry_run,
                },
            )

        except Exception as e:
            logger.error("Memory cleanup failed: %s", e)
            return ActionResult(
                action_id="cleanup.agent_memory", ok=False, data={"error": str(e)}
            )

    @atomic_action(
        action_id="cleanup.action_results",
        intent="Prune old operational action results",
        impact=ActionImpact.WRITE_DATA,
        policies=["atomic_actions"],
    )
    # ID: 5e76777a-ca1d-424f-9853-acbee0967c6e
    async def cleanup_action_results(
        self, days_to_keep: int = 7, dry_run: bool = True
    ) -> ActionResult:
        """
        Removes old records from core.action_results to keep the ledger relevant.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        try:
            if dry_run:
                query = text(
                    "SELECT COUNT(*) FROM core.action_results WHERE created_at < :cutoff"
                )
                res = await self.session.execute(query, {"cutoff": cutoff})
                count = res.scalar_one()
            else:
                query = text(
                    "DELETE FROM core.action_results WHERE created_at < :cutoff"
                )
                res = await self.session.execute(query, {"cutoff": cutoff})
                count = res.rowcount

            return ActionResult(
                action_id="cleanup.action_results",
                ok=True,
                data={
                    "records_processed": count,
                    "dry_run": dry_run,
                    "retention_days": days_to_keep,
                },
            )
        except Exception as e:
            logger.error("Action results cleanup failed: %s", e)
            return ActionResult(
                action_id="cleanup.action_results", ok=False, data={"error": str(e)}
            )
