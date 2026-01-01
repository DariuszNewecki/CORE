# src/shared/infrastructure/repositories/vector_link_repository.py
"""
Repository for symbol-vector link management.
Enforces db.write_via_governed_cli constitutional rule.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: template_value
# ID: d1c4233c-25d9-4378-84fc-d529bbbe89e6
class VectorLinkRepository:
    """
    Repository for managing symbol_vector_links table.

    Constitutional: Separates data access from business logic.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ID: 76ae2292-5b84-47c8-81e6-f5b12060b809
    async def delete_dangling_links(self, dangling_links: list[tuple[str, str]]) -> int:
        """
        Delete dangling links from core.symbol_vector_links.

        Args:
            dangling_links: List of (symbol_id, vector_id) tuples

        Returns:
            Count of deleted links

        Note: Does NOT commit - caller manages transaction.
        """
        count = 0
        for symbol_id, vector_id in dangling_links:
            await self.session.execute(
                text(
                    """
                    DELETE FROM core.symbol_vector_links
                    WHERE symbol_id = :symbol_id
                      AND vector_id = :vector_id::uuid
                """
                ),
                {"symbol_id": symbol_id, "vector_id": vector_id},
            )
            count += 1

        logger.info("Deleted %d dangling links (not yet committed)", count)
        return count

    # ID: beb0192f-3b36-41f4-9418-3e8e95d3736b
    async def get_all_links(self) -> list[tuple[str, str]]:
        """Get all symbol-vector links as (symbol_id, vector_id) tuples."""
        result = await self.session.execute(
            text(
                """
                SELECT symbol_id, vector_id::text
                FROM core.symbol_vector_links
            """
            )
        )
        return [(row.symbol_id, row.vector_id) for row in result]

    # ID: 9d73006e-a319-43c9-b3c3-82f923f7a44e
    async def get_all_vector_ids(self) -> set[str]:
        """Get all unique vector IDs referenced in links."""
        result = await self.session.execute(
            text(
                """
                SELECT DISTINCT vector_id::text
                FROM core.symbol_vector_links
            """
            )
        )
        return {row.vector_id for row in result}
