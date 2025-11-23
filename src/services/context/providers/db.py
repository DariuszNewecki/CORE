# src/services/context/providers/db.py

"""DBProvider - Fetches symbols from PostgreSQL.

Wraps existing database service for context building.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from typing import Any

from sqlalchemy import select, text

from services.database.models import Symbol

# --- START OF FIX: Import the session manager ---
from services.database.session_manager import get_session

# --- END OF FIX ---

logger = logging.getLogger(__name__)


# ID: b0a16299-e125-421a-a4c1-a95f41b8c022
class DBProvider:
    """Provides symbol data from database."""

    # --- START OF FIX: Remove the session from the constructor ---
    def __init__(self):
        """Initializes the provider without a persistent database session."""
        pass

    # --- END OF FIX ---

    def _format_symbol_as_context_item(self, row) -> dict:
        """
        Helper to convert a database row from core.symbols into the
        standard context item dictionary format.
        """
        if not row:
            return {}

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
                "health": getattr(row, "health_status", "unknown"),
            },
        }

    # ID: 55c25e2c-8998-49db-bec1-beab8ea81c49
    async def get_related_symbols(self, symbol_id: str, depth: int) -> list[dict]:
        """
        Fetches related symbols by traversing the knowledge graph within the database.
        """
        if depth == 0:
            return []

        logger.info(f"Graph traversal for symbol {symbol_id} to depth {depth}")
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
            # --- START OF FIX: Acquire a session for this specific query ---
            async with get_session() as db:
                result = await db.execute(
                    recursive_query, {"symbol_id": symbol_id, "depth": depth}
                )
                related_symbols = [
                    self._format_symbol_as_context_item(row)
                    for row in result.mappings()
                ]
            # --- END OF FIX ---
            logger.info(
                f"Found {len(related_symbols)} related symbols via graph traversal."
            )
            return related_symbols
        except Exception as e:
            logger.error(f"Graph traversal query failed: {e}", exc_info=True)
            return []

    # ID: 03bc6c96-7ad3-4b08-9faa-d281289807b7
    async def get_symbols_for_scope(
        self, scope: dict[str, Any], max_items: int = 50
    ) -> list[dict[str, Any]]:
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

            # --- START OF FIX: Acquire a session for this set of queries ---
            async with get_session() as db:
                for pattern, priority in sorted(query_parts, key=lambda x: x[1]):
                    if len(all_symbols) >= max_items:
                        break
                    limit = 100 if priority == 1 else max_items - len(all_symbols)
                    stmt = (
                        select(Symbol)
                        .where(Symbol.is_public, Symbol.module.like(pattern))
                        .limit(limit)
                    )
                    result = await db.execute(stmt)
                    rows = result.scalars().all()

                    for row in rows:
                        if row.id in seen_symbol_ids:
                            continue
                        seen_symbol_ids.add(row.id)
                        file_path = "src/" + row.module.replace(".", "/") + ".py"
                        if any(fnmatch(file_path, exc) for exc in excludes):
                            continue
                        all_symbols.append(self._format_symbol_as_context_item(row))
            # --- END OF FIX ---
            logger.info(
                f"Retrieved {len(all_symbols)} symbols from DB (prioritized by scope)"
            )
            return all_symbols
        except Exception as e:
            logger.error(f"DB query for scope failed: {e}", exc_info=True)
            return []

    # ID: 83f8df77-84cd-498a-b798-e674fe2dc1cf
    async def get_symbol_by_name(self, name: str) -> dict[str, Any] | None:
        try:
            # --- START OF FIX: Acquire a session for this query ---
            async with get_session() as db:
                stmt = select(Symbol).where(Symbol.qualname == name).limit(1)
                result = await db.execute(stmt)
                row = result.scalars().first()
            # --- END OF FIX ---
            return self._format_symbol_as_context_item(row) if row else None
        except Exception as e:
            logger.error(f"Symbol lookup failed: {e}", exc_info=True)
            return None
