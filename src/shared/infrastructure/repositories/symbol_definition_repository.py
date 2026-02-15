# src/shared/infrastructure/repositories/symbol_definition_repository.py
"""
Repository for symbol definition/capability assignment operations.
Enforces db.write_via_governed_cli constitutional rule.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 94428728-0eff-440d-b517-2f2ec9857d22
# ID: 016d84c9-26b9-466d-b071-84c160f64629
class SymbolDefinitionRepository:
    """
    Repository for symbol definition status and capability key management.

    Constitutional: Separates data access from business logic.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ID: 0b03bdea-3be5-42be-87ab-6711782c15b5
    async def mark_attempt(
        self,
        symbol_id: Any,
        *,
        status: str,
        error: str | None = None,
        key: str | None = None,
    ) -> None:
        """
        Update symbol definition attempt tracking.

        Args:
            symbol_id: Symbol ID to update
            status: New status (e.g., 'defined', 'invalid', 'pending')
            error: Optional error message
            key: Optional capability key

        Note: Does NOT commit - caller manages transaction.
        """
        await self.session.execute(
            text(
                """
                UPDATE core.symbols
                SET
                    definition_status = :status,
                    definition_error = :error,
                    key = :key,
                    definition_source = 'llm',
                    defined_at = CASE WHEN :status = 'defined' THEN NOW() ELSE NULL END,
                    last_attempt_at = NOW(),
                    attempt_count = attempt_count + 1
                WHERE id = :id
            """
            ),
            {"id": symbol_id, "status": status, "error": error, "key": key},
        )

        logger.debug(
            "Marked symbol %s attempt: status=%s, key=%s (not yet committed)",
            symbol_id,
            status,
            key,
        )

    # ID: a8832d98-f18c-46e7-bf84-b07b7bdd5f44
    async def mark_stale_symbols_broken(self, symbol_ids: list[Any]) -> int:
        """
        Mark symbols as broken (files no longer exist).

        Args:
            symbol_ids: List of symbol IDs to mark as broken

        Returns:
            Count of updated symbols

        Note: Does NOT commit - caller manages transaction.
        """
        if not symbol_ids:
            return 0

        await self.session.execute(
            text(
                """
                UPDATE core.symbols
                SET health_status = 'broken',
                    updated_at = NOW()
                WHERE id = ANY(:ids)
            """
            ),
            {"ids": symbol_ids},
        )

        count = len(symbol_ids)
        logger.info("Marked %d stale symbols as 'broken' (not yet committed)", count)
        return count

    # ID: aeaaded3-ca5d-4bb4-af7e-414b32e21d45
    async def get_undefined_symbols(
        self, limit: int = 500, tier_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get symbols that need capability definition.

        Args:
            limit: Maximum number of symbols to return
            tier_filter: Optional tier filter

        Returns:
            List of symbol records as dictionaries
        """
        # Build query with optional tier filter
        tier_condition = ""
        if tier_filter:
            tier_condition = "AND tier = :tier"

        result = await self.session.execute(
            text(
                f"""
                SELECT
                    id,
                    symbol_path,
                    file_path,
                    qualname,
                    module,
                    definition_status,
                    attempt_count
                FROM core.symbols
                WHERE
                    is_public = TRUE
                    AND definition_status IN ('pending', 'invalid')
                    AND health_status != 'broken'
                    {tier_condition}
                    AND (
                        last_attempt_at IS NULL
                        OR last_attempt_at < NOW() - INTERVAL '1 hour'
                    )
                ORDER BY
                    attempt_count ASC,
                    last_attempt_at NULLS FIRST,
                    qualname
                LIMIT :limit
            """
            ),
            {"limit": limit, "tier": tier_filter} if tier_filter else {"limit": limit},
        )

        symbols = [dict(row._mapping) for row in result]
        logger.info(
            "Found %d symbols needing definition (tier=%s, limit=%d)",
            len(symbols),
            tier_filter or "any",
            limit,
        )
        return symbols
