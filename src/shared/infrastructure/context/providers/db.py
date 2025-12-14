# src/shared/infrastructure/context/providers/db.py

"""DBProvider - Fetches symbols from PostgreSQL.

Wraps existing database service for context building.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from fnmatch import fnmatch
from typing import Any

from sqlalchemy import select, text

from shared.infrastructure.database.models import Symbol
from shared.infrastructure.database.session_manager import get_session


logger = logging.getLogger(__name__)


# ID: cf20cce3-768d-4ab6-87e8-51f45928dd7e
class DBProvider:
    """Provides symbol data from database.

    This provider is intentionally light-weight and stateless. It acquires
    database sessions on demand via `get_session()`.

    For backward compatibility, it accepts an optional `db_service` argument
    but does not require it. Older call sites that instantiated
    `DBProvider(db_service=...)` will continue to work.
    """

    def __init__(self, db_service: Any | None = None):
        """Initializes the provider.

        Args:
            db_service: Optional legacy database service instance. Currently
                unused by the new implementation, but accepted for backward
                compatibility to avoid constructor errors.
        """
        self.db_service = db_service

    def _format_symbol_as_context_item(self, row) -> dict:
        """Convert a database row into standard context item format."""
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

    def _build_module_pattern(self, pattern: str, pattern_type: str) -> str:
        """Convert file path pattern to SQL LIKE module pattern."""
        if pattern_type == "include":
            module_pattern = (
                pattern.replace("src/", "").replace("/", "").replace(".py", "")
            )
            if not module_pattern.endswith("%"):
                module_pattern += "%"
            return module_pattern
        else:
            return pattern.replace("src/", "").replace("/", ".").rstrip(".") + "%"

    def _should_exclude_file(self, file_path: str, exclude_patterns: list) -> bool:
        """Check if file path matches any exclude pattern."""
        return any(fnmatch(file_path, pattern) for pattern in exclude_patterns)

    async def _execute_graph_traversal_query(
        self, symbol_id: str, depth: int
    ) -> list[dict]:
        """Execute recursive graph traversal query."""
        recursive_query = text(
            "\n            WITH RECURSIVE symbol_graph AS (\n                SELECT id, qualname, calls, 0 as depth\n                FROM core.symbols\n                WHERE id = :symbol_id\n\n                UNION ALL\n\n                SELECT s.id, s.qualname, s.calls, sg.depth + 1\n                FROM core.symbols s, symbol_graph sg\n                WHERE sg.depth < :depth AND (\n                    s.qualname = ANY(SELECT jsonb_array_elements_text(sg.calls))\n                    OR EXISTS (\n                        SELECT 1\n                        FROM jsonb_array_elements_text(s.calls) AS elem\n                        WHERE elem ->> 0 = sg.qualname\n                    )\n                )\n            )\n            SELECT s.*\n            FROM core.symbols s\n            JOIN (\n                SELECT DISTINCT id\n                FROM symbol_graph\n            ) AS unique_related_ids\n            ON s.id = unique_related_ids.id\n            WHERE s.id != :symbol_id;\n        "
        )
        async with get_session() as db:
            result = await db.execute(
                recursive_query, {"symbol_id": symbol_id, "depth": depth}
            )
            return [
                self._format_symbol_as_context_item(row) for row in result.mappings()
            ]

    # ID: cbdd5c76-f03c-432e-accf-cc75d956eacc
    async def get_related_symbols(self, symbol_id: str, depth: int) -> list[dict]:
        """Fetch related symbols by traversing the knowledge graph."""
        if depth == 0:
            return []
        logger.info("Graph traversal for symbol %s to depth %s", symbol_id, depth)
        try:
            related_symbols = await self._execute_graph_traversal_query(
                symbol_id, depth
            )
            logger.info(
                "Found %d related symbols via graph traversal.", len(related_symbols)
            )
            return related_symbols
        except Exception as e:
            logger.error("Graph traversal query failed: %s", e, exc_info=True)
            return []

    def _build_query_patterns(self, scope: dict[str, Any]) -> list[tuple[str, int]]:
        """Build SQL LIKE patterns from scope definition."""
        roots = scope.get("roots", [])
        includes = scope.get("include", [])
        query_parts = []
        for include in includes:
            module_pattern = self._build_module_pattern(include, "include")
            query_parts.append((module_pattern, 1))
        for root in roots:
            module_pattern = self._build_module_pattern(root, "root")
            query_parts.append((module_pattern, 2))
        if not query_parts:
            query_parts = [("%", 3)]
        return sorted(query_parts, key=lambda x: x[1])

    async def _fetch_symbols_for_pattern(
        self,
        pattern: str,
        priority: int,
        max_items: int,
        current_count: int,
        seen_ids: set,
        exclude_patterns: list,
    ) -> tuple[list[dict], int, set]:
        """Fetch symbols matching a specific pattern."""
        if current_count >= max_items:
            return ([], current_count, seen_ids)
        limit = 100 if priority == 1 else max_items - current_count
        symbols = []
        async with get_session() as db:
            stmt = (
                select(Symbol)
                .where(Symbol.is_public, Symbol.module.like(pattern))
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                if row.id in seen_ids:
                    continue
                seen_ids.add(row.id)
                file_path = f"src/{row.module.replace('.', '/')}.py"
                if self._should_exclude_file(file_path, exclude_patterns):
                    continue
                symbols.append(self._format_symbol_as_context_item(row))
                current_count += 1
                if current_count >= max_items:
                    break
        return (symbols, current_count, seen_ids)

    async def _try_exact_symbol_matches(
        self, includes: list[str]
    ) -> list[dict[str, Any]]:
        """
        Attempt exact symbol name lookups for include patterns.

        If a pattern looks like a symbol name (no paths, no wildcards),
        try finding it as an exact qualname match.

        Returns:
            List of exact matches found
        """
        exact_matches = []
        for pattern in includes:
            if "/" in pattern or "*" in pattern or "%" in pattern:
                continue
            match = await self.get_symbol_by_name(pattern)
            if match:
                logger.info("Found exact symbol match: %s", pattern)
                exact_matches.append(match)
        return exact_matches

    # ID: 566aa199-d7e1-494d-ae87-fa53a0c17870
    async def get_symbols_for_scope(
        self, scope: dict[str, Any], max_items: int = 50
    ) -> list[dict[str, Any]]:
        """
        Retrieve symbols matching a given scope definition.

        Strategy:
        1. First, try exact symbol name matches for simple patterns
        2. Then do fuzzy module pattern matching for remaining quota
        3. Prioritize exact matches at the front of results
        """
        try:
            includes = scope.get("include", [])
            excludes = scope.get("exclude", [])
            exact_matches = await self._try_exact_symbol_matches(includes)
            if exact_matches:
                logger.info("Prioritizing %s exact symbol matches", len(exact_matches))
            remaining_quota = max_items - len(exact_matches)
            query_patterns = self._build_query_patterns(scope)
            fuzzy_symbols = []
            seen_symbol_ids = {item["metadata"]["symbol_id"] for item in exact_matches}
            current_count = len(exact_matches)
            for pattern, priority in query_patterns:
                (
                    symbols,
                    current_count,
                    seen_symbol_ids,
                ) = await self._fetch_symbols_for_pattern(
                    pattern,
                    priority,
                    max_items,
                    current_count,
                    seen_symbol_ids,
                    excludes,
                )
                fuzzy_symbols.extend(symbols)
                if current_count >= max_items:
                    break
            all_symbols = exact_matches + fuzzy_symbols
            logger.info(
                "Retrieved %d symbols from DB (%d exact, %d fuzzy).",
                len(all_symbols),
                len(exact_matches),
                len(fuzzy_symbols),
            )
            return all_symbols
        except Exception as e:
            logger.error("DB query for scope failed: %s", e, exc_info=True)
            return []

    # ID: c407d3a9-c1be-414e-85f9-c40a300acd75
    async def get_symbol_by_name(self, name: str) -> dict[str, Any] | None:
        """Look up a symbol by its fully-qualified name (qualname)."""
        try:
            async with get_session() as db:
                stmt = select(Symbol).where(Symbol.qualname == name).limit(1)
                result = await db.execute(stmt)
                row = result.scalars().first()
            return self._format_symbol_as_context_item(row) if row else None
        except Exception as e:
            logger.error("Symbol lookup failed: %s", e, exc_info=True)
            return None
