# src/shared/infrastructure/repositories/memory_repository.py
"""
Repository for agent memory tables (episodes, decisions, reflections).
Enforces db.write_via_governed_cli constitutional rule.

Constitutional Principle: Transaction boundaries at controller layer, not service layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: template_value
# ID: 9cf9287b-cc80-4121-a307-bffa7e6b925c
class MemoryRepository:
    """
    Repository for agent memory persistence.

    Services use this to execute data operations.
    Controllers manage transaction boundaries (commit/rollback).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ID: 127b6936-f1a3-4f6e-8937-ede3f645a4a1
    async def delete_old_episodes(self, cutoff_date: datetime) -> int:
        """
        Delete episodes older than cutoff date.
        Returns count of deleted rows.
        Does NOT commit - caller manages transaction.
        """
        # Delete decisions first (FK dependency)
        decisions_sql = text(
            """
            DELETE FROM agent_decisions
            WHERE episode_id IN (
                SELECT id FROM agent_episodes WHERE created_at < :cutoff
            )
        """
        )
        decisions_result = await self.session.execute(
            decisions_sql, {"cutoff": cutoff_date}
        )
        decisions_count = decisions_result.rowcount

        # Delete episodes
        episodes_sql = text("DELETE FROM agent_episodes WHERE created_at < :cutoff")
        episodes_result = await self.session.execute(
            episodes_sql, {"cutoff": cutoff_date}
        )
        episodes_count = episodes_result.rowcount

        logger.info(
            "Deleted %d episodes and %d decisions (not yet committed)",
            episodes_count,
            decisions_count,
        )

        return episodes_count

    # ID: 0a06a7d1-2110-46ac-b258-9318da729c10
    async def delete_old_reflections(
        self, cutoff_date: datetime, min_confidence: float = 0.3
    ) -> int:
        """
        Delete reflections older than cutoff or with low confidence.
        Returns count of deleted rows.
        Does NOT commit - caller manages transaction.
        """
        reflections_sql = text(
            """
            DELETE FROM agent_reflections
            WHERE created_at < :cutoff
               OR (confidence_score < :min_conf AND created_at < :recent_cutoff)
        """
        )

        # Keep recent reflections even if low confidence (30 days)
        recent_cutoff = datetime.utcnow() - timedelta(days=30)

        result = await self.session.execute(
            reflections_sql,
            {
                "cutoff": cutoff_date,
                "min_conf": min_confidence,
                "recent_cutoff": recent_cutoff,
            },
        )

        count = result.rowcount
        logger.info("Deleted %d reflections (not yet committed)", count)
        return count

    # ID: 16a1e5e2-1915-4f18-9d69-14f45a83f18f
    async def count_episodes_older_than(self, cutoff_date: datetime) -> int:
        """Count how many episodes would be deleted (for dry-run)."""
        sql = text("SELECT COUNT(*) FROM agent_episodes WHERE created_at < :cutoff")
        result = await self.session.execute(sql, {"cutoff": cutoff_date})
        return result.scalar_one()

    # ID: 5fd346ec-6dd0-4ae1-949d-d5ae9e392d05
    async def count_reflections_older_than(
        self, cutoff_date: datetime, min_confidence: float = 0.3
    ) -> int:
        """Count how many reflections would be deleted (for dry-run)."""
        sql = text(
            """
            SELECT COUNT(*) FROM agent_reflections
            WHERE created_at < :cutoff
               OR (confidence_score < :min_conf AND created_at < :recent_cutoff)
        """
        )
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        result = await self.session.execute(
            sql,
            {
                "cutoff": cutoff_date,
                "min_conf": min_confidence,
                "recent_cutoff": recent_cutoff,
            },
        )
        return result.scalar_one()
