# src/services/context/providers/db.py

"""DBProvider - Fetches symbols from PostgreSQL.

Wraps existing database service for context building.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import Symbol

logger = logging.getLogger(__name__)


# ID: 0996b285-2ca9-41ef-aa35-1baf2f706b3a
class DBProvider:
    """Provides symbol data from database."""

    def __init__(self, db_service: AsyncSession | None = None):
        self.db = db_service

    def _format_symbol_as_context_item(self, row) -> dict:
        """
        Helper to convert a database row from core.symbols into the
        standard context item dictionary format.
        """
        module_path = row.module.replace(".", "/")
        file_path = f"src/{module_path}.py"

        return {
            "name": row.qualname,
            "path": file_path,
            "item_type": "symbol",
            "signature": row.ast_signature,
            "summary": row.intent or f"{row.kind} in {row.module}",
            "source": "db_graph_traversal",
            "metadata": {
                "symbol_id": str(row.id),
                "kind": row.kind,
                "health": row.health_status,
            },
        }

    # --- START OF THE FINAL, CORRECTED METHOD ---
    # ID: 56e8783a-1a7e-46d1-8e08-f129d43cc709
    async def get_related_symbols(self, symbol_id: str, depth: int) -> list[dict]:
        """
        Fetches related symbols (callers and callees) up to a specified depth
        by traversing the knowledge graph within the database.
        """
        if not self.db or depth == 0:
            return []

        logger.info(f"Graph traversal for symbol {symbol_id} to depth {depth}")

        # This recursive query correctly traverses the `calls` JSONB array.
        recursive_query = text(
            """
            WITH RECURSIVE symbol_graph AS (
                -- Anchor member: the starting symbol
                SELECT id, qualname, calls, 0 as depth
                FROM core.symbols
                WHERE id = :symbol_id

                UNION ALL

                -- Recursive member: find callers and callees
                SELECT s.id, s.qualname, s.calls, sg.depth + 1
                FROM core.symbols s, symbol_graph sg
                WHERE sg.depth < :depth AND (
                    -- s is a callee of sg (a dependency)
                    s.qualname = ANY(SELECT jsonb_array_elements_text(sg.calls))
                    OR
                    -- s is a caller of sg (a dependent)
                    EXISTS (SELECT 1 FROM jsonb_array_elements_text(s.calls) as elem WHERE elem ->> 0 = sg.qualname)
                )
            )
            -- Select the final set of related symbols, excluding the start symbol
            SELECT s.*
            FROM core.symbols s
            JOIN (SELECT DISTINCT id FROM symbol_graph) AS unique_related_ids ON s.id = unique_related_ids.id
            WHERE s.id != :symbol_id;
        """
        )

        try:
            result = await self.db.execute(
                recursive_query, {"symbol_id": symbol_id, "depth": depth}
            )
            # Use mappings() to get dict-like rows that work with the formatter
            related_symbols = [
                self._format_symbol_as_context_item(row) for row in result.mappings()
            ]
            logger.info(
                f"Found {len(related_symbols)} related symbols via graph traversal."
            )
            return related_symbols
        except Exception as e:
            logger.error(f"Graph traversal query failed: {e}", exc_info=True)
            return []

    # --- END OF THE FINAL, CORRECTED METHOD ---

    # ID: 156881a0-d88b-47b3-bd61-e8cf7e20a4f8
    async def get_symbols_for_scope(
        self, scope: dict[str, Any], max_items: int = 50
    ) -> list[dict[str, Any]]:
        if not self.db:
            return []
        try:
            roots = scope.get("roots", [])
            includes = scope.get("include", [])
            excludes = scope.get("exclude", [])
            query_parts = []

            for include in includes:
                module_pattern = (
                    include.replace("src/", "").replace("/", ".").replace(".py", "")
                )
                if not module_pattern.endswith("%"):
                    module_pattern += "%"
                query_parts.append((module_pattern, 1))

            for root in roots:
                module_pattern = (
                    root.replace("src/", "").replace("/", ".").rstrip(".") + "%"
                )
                query_parts.append((module_pattern, 2))

            if not query_parts:
                query_parts = [("%", 3)]

            all_symbols: list[dict[str, Any]] = []
            seen_symbol_ids = set()

            for pattern, priority in sorted(query_parts, key=lambda x: x[1]):
                if len(all_symbols) >= max_items:
                    break
                limit = 100 if priority == 1 else max_items - len(all_symbols)
                stmt = (
                    select(Symbol)
                    .where(Symbol.is_public, Symbol.module.like(pattern))
                    .limit(limit)
                )
                result = await self.db.execute(stmt)
                rows = result.scalars().all()

                for row in rows:
                    if row.id in seen_symbol_ids:
                        continue
                    seen_symbol_ids.add(row.id)
                    file_path = "src/" + row.module.replace(".", "/") + ".py"
                    if any(fnmatch(file_path, exc) for exc in excludes):
                        continue
                    # Use the formatter here as well for consistency
                    all_symbols.append(self._format_symbol_as_context_item(row))

            logger.info(
                f"Retrieved {len(all_symbols)} symbols from DB (prioritized by scope)"
            )
            return all_symbols
        except Exception as e:
            logger.error(f"DB query for scope failed: {e}", exc_info=True)
            return []

    # ID: 3176d7e0-ac1a-4acd-87e0-924c7ad956c1
    async def get_symbol_by_name(self, name: str) -> dict[str, Any] | None:
        if not self.db:
            return None
        try:
            stmt = select(Symbol).where(Symbol.qualname == name).limit(1)
            result = await self.db.execute(stmt)
            row = result.scalars().first()
            return self._format_symbol_as_context_item(row) if row else None
        except Exception as e:
            logger.error(f"Symbol lookup failed: {e}", exc_info=True)
            return None
