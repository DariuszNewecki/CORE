# src/shared/infrastructure/context/database.py

"""ContextDatabase - persistence layer for context packet metadata."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().context


# ID: 9871ed94-1611-429b-a12b-63eb65417a23
class ContextDatabase:
    """Manages database persistence for context packet metadata."""

    def __init__(self) -> None:
        self.db: AsyncSession | None = None

    # ID: 7dd22172-8894-4835-a8f8-d854d4a2051b
    async def get_stats(self) -> dict[str, Any]:
        if not self.db:
            return {}

        try:
            query = text(
                """
                SELECT
                    COUNT(*) AS total_packets,
                    COUNT(DISTINCT task_id) AS unique_tasks,
                    AVG(tokens_est) AS avg_tokens,
                    AVG(build_ms) AS avg_build_ms,
                    AVG(items_count) AS avg_items,
                    SUM(redactions_count) AS total_redactions
                FROM core.context_packets
                """
            )
            result = await self.db.execute(query)
            row = result.mappings().first()
            return dict(row) if row else {}
        except Exception as e:
            logger.error("Failed to retrieve stats: %s", e)
            return {}
