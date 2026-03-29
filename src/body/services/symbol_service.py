# src/body/services/symbol_service.py
"""
SymbolService - Data-access layer for core.symbols (capability tagging).

Covers:
  - CapabilityTaggerWorker._fetch_untagged_symbols
  - CapabilityTaggerWorker._tag_symbols (UPDATE loop)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5fa7ca27-3636-48c8-87af-6dba94427689
class SymbolService:
    """
    Body layer service. Exposes named methods for core.symbols operations
    used by CapabilityTaggerWorker.
    """

    # ID: 8cd068da-396e-47d9-a241-f4a3c3633a21
    async def fetch_untagged_symbols(self, batch_size: int) -> list[dict[str, Any]]:
        """
        Return up to *batch_size* public, non-deprecated symbols with no
        capability key assigned, ordered by symbol_path.

        Covers:
          - CapabilityTaggerWorker._fetch_untagged_symbols
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, symbol_path, qualname, file_path,
                        kind, domain, docstring, is_public, calls
                    FROM core.symbols
                    WHERE key IS NULL
                      AND is_public = true
                      AND state != 'deprecated'
                      AND file_path IS NOT NULL
                      AND file_path != ''
                    ORDER BY symbol_path
                    LIMIT :batch_size
                    """
                ),
                {"batch_size": batch_size},
            )
            return [dict(row) for row in result.mappings().all()]

    # ID: a47395b5-daea-43f4-94eb-515619cc9678
    async def apply_symbol_keys(self, assignments: list[dict[str, str]]) -> int:
        """
        Batch-update capability keys for a list of symbols in a single
        transaction. Only updates rows where key IS NULL (idempotent).

        *assignments* is a list of dicts with keys ``id`` (UUID str) and
        ``key`` (dotted capability key string).

        Returns the number of UPDATE statements issued (not affected rows).

        Covers:
          - CapabilityTaggerWorker._tag_symbols — UPDATE core.symbols loop
        """
        from body.services.service_registry import ServiceRegistry

        if not assignments:
            return 0

        async with ServiceRegistry.session() as session:
            async with session.begin():
                for assignment in assignments:
                    await session.execute(
                        text(
                            """
                            UPDATE core.symbols
                            SET key = :key, updated_at = NOW()
                            WHERE id = cast(:id as uuid)
                              AND key IS NULL
                            """
                        ),
                        {"key": assignment["key"], "id": assignment["id"]},
                    )
        return len(assignments)
