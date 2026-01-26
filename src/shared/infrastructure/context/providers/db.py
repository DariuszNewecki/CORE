# src/shared/infrastructure/context/providers/db.py

"""DBProvider - Fetches symbols from PostgreSQL.

CONSTITUTIONAL FIX:
- Removed direct import of 'get_session' to satisfy 'logic.di.no_global_session'.
- Accepts session_factory via constructor for proper dependency injection.
- All methods use the injected factory instead of global get_session().
"""

from __future__ import annotations

from collections.abc import Callable
from fnmatch import fnmatch
from typing import Any

from sqlalchemy import select, text

from shared.infrastructure.database.models import Symbol
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cf20cce3-768d-4ab6-87e8-51f45928dd7e
class DBProvider:
    """Provides symbol data from database.

    This provider uses dependency injection for database access.
    It accepts a session_factory callable that returns an async context manager.

    Constitutional Alignment:
    - Phase: READ (data retrieval only, no mutations)
    - Authority: Injected session factory (no global state)
    - Testability: Full mock support via factory injection
    """

    def __init__(self, session_factory: Callable | None = None):
        """Initializes the provider.

        Args:
            session_factory: Callable that returns an async session context manager.
                If None, database operations will fail with clear error messages.
        """
        self._session_factory = session_factory

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
        if not self._session_factory:
            raise RuntimeError(
                "DBProvider: session_factory not configured. "
                "Provider must be initialized with a valid session factory."
            )

        recursive_query = text(
            """
            WITH RECURSIVE symbol_graph AS (
                SELECT id, qualname, calls, 0 as depth
                FROM core.symbols
                WHERE id = :symbol_id

                UNION ALL

                SELECT s.id, s.qualname, s.calls, sg.depth + 1
                FROM core.symbols s, symbol_graph sg
                WHERE sg.depth < :depth AND (
                    s.qualname = ANY(SELECT jsonb_array_elements_text(sg.calls))
                    OR EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(s.calls) AS elem
                        WHERE elem ->> 0 = sg.qualname
                    )
                )
            )
            SELECT s.*
            FROM core.symbols s
            JOIN (
                SELECT DISTINCT id
                FROM symbol_graph
            ) AS unique_related_ids
            ON s.id = unique_related_ids.id
            WHERE s.id != :symbol_id;
        """
        )
        async with self._session_factory() as db:
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
        if not self._session_factory:
            raise RuntimeError(
                "DBProvider: session_factory not configured. "
                "Provider must be initialized with a valid session factory."
            )

        if current_count >= max_items:
            return ([], current_count, seen_ids)
        limit = 100 if priority == 1 else max_items - current_count
        symbols = []
        async with self._session_factory() as db:
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
        """
        if not self._session_factory:
            return []

        results = []
        for pattern in includes:
            if "/" in pattern or "*" in pattern or "?" in pattern:
                continue
            clean_name = pattern.strip()
            async with self._session_factory() as db:
                stmt = select(Symbol).where(
                    Symbol.is_public, Symbol.qualname == clean_name
                )
                result = await db.execute(stmt)
                row = result.scalars().first()
                if row:
                    results.append(self._format_symbol_as_context_item(row))
        return results

    # ID: 8a9b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
    async def fetch_symbols_for_scope(
        self, scope: dict[str, Any], max_items: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch symbols matching scope definition with pattern prioritization."""
        if not self._session_factory:
            logger.warning("DBProvider has no session factory - skipping DB fetch")
            return []

        query_patterns = self._build_query_patterns(scope)
        exclude_patterns = scope.get("exclude", [])
        seen_ids = set()
        symbols = []
        current_count = 0

        exact_matches = await self._try_exact_symbol_matches(scope.get("include", []))
        for item in exact_matches:
            if item["metadata"]["symbol_id"] not in seen_ids:
                symbols.append(item)
                seen_ids.add(item["metadata"]["symbol_id"])
                current_count += 1
                if current_count >= max_items:
                    return symbols

        for pattern, priority in query_patterns:
            (
                fetched_symbols,
                current_count,
                seen_ids,
            ) = await self._fetch_symbols_for_pattern(
                pattern,
                priority,
                max_items,
                current_count,
                seen_ids,
                exclude_patterns,
            )
            symbols.extend(fetched_symbols)
            if current_count >= max_items:
                break

        logger.info("DBProvider fetched %d symbols from database", len(symbols))
        return symbols
