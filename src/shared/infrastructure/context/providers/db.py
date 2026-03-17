# src/shared/infrastructure/context/providers/db.py

"""
DBProvider - fetches symbol evidence from PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select, text

from shared.infrastructure.database.models import Symbol
from shared.logger import getLogger


logger = getLogger(__name__)


class _SQLRegistry:
    """Build SQL fragments for database-backed context retrieval."""

    GRAPH_TRAVERSAL = text(
        """
        WITH RECURSIVE symbol_graph AS (
            SELECT id, qualname, calls, 0 AS depth
            FROM core.symbols
            WHERE id = :symbol_id

            UNION ALL

            SELECT s.id, s.qualname, s.calls, sg.depth + 1
            FROM core.symbols s, symbol_graph sg
            WHERE sg.depth < :depth
              AND (
                    s.qualname = ANY(
                        SELECT jsonb_array_elements_text(sg.calls)
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(s.calls) AS elem
                        WHERE elem = sg.qualname
                    )
                  )
        )
        SELECT s.*
        FROM core.symbols s
        JOIN (SELECT DISTINCT id FROM symbol_graph) AS ids ON s.id = ids.id
        WHERE s.id != :symbol_id;
        """
    )

    @staticmethod
    # ID: f2e9fe0c-0629-4685-88a0-8baa4272722d
    def build_module_pattern(path: str) -> str:
        pattern = (
            path.replace("src/", "").replace("/", ".").replace(".py", "").strip(".")
        )
        return f"{pattern}%" if pattern else "%"


# ID: cc3d11db-9752-4031-ba67-4a08235ef5ee
class DBProvider:
    """Provides database-backed symbol evidence."""

    def __init__(self, session_factory: Callable | None = None) -> None:
        self._session_factory = session_factory

    # ID: da1254e0-fff8-43c1-8785-02f93cf9beae
    async def fetch_symbols_for_scope(
        self,
        scope: dict[str, Any],
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        if not self._session_factory:
            return []

        includes = scope.get("include", [])
        patterns = [(_SQLRegistry.build_module_pattern(p), 1) for p in includes] or [
            ("%", 1)
        ]

        evidence: list[dict[str, Any]] = []
        seen: set[str] = set()

        async with self._session_factory() as db:
            for pattern, _ in patterns:
                stmt = (
                    select(Symbol)
                    .where(Symbol.is_public, Symbol.module.like(pattern))
                    .limit(max_items)
                )
                result = await db.execute(stmt)

                for row in result.scalars().all():
                    item = self._format_symbol_row(row)
                    dedupe_key = f"{item['name']}::{item['path']}"
                    if dedupe_key in seen:
                        continue

                    evidence.append(item)
                    seen.add(dedupe_key)

                    if len(evidence) >= max_items:
                        return evidence

        return evidence

    # ID: 3560f987-718b-409d-bd20-e98cc4c5f7c9
    async def get_related_symbols(
        self,
        symbol_id: str,
        depth: int,
    ) -> list[dict[str, Any]]:
        if depth <= 0 or not self._session_factory:
            return []

        async with self._session_factory() as db:
            result = await db.execute(
                _SQLRegistry.GRAPH_TRAVERSAL,
                {"symbol_id": symbol_id, "depth": depth},
            )
            return [self._format_mapping_row(row) for row in result.mappings().all()]

    def _format_symbol_row(self, row: Any) -> dict[str, Any]:
        module = getattr(row, "module", "") or ""
        qualname = getattr(row, "qualname", "") or ""

        return {
            "name": qualname,
            "path": f"src/{module.replace('.', '/')}.py" if module else "",
            "item_type": "symbol",
            "content": None,
            "signature": getattr(row, "ast_signature", "") or "",
            "summary": getattr(row, "intent", "") or "",
            "source": "database",
            "symbol_path": qualname,
            "metadata": {
                "symbol_id": str(getattr(row, "id", "")),
                "kind": getattr(row, "kind", "function"),
            },
        }

    def _format_mapping_row(self, row: Any) -> dict[str, Any]:
        module = row.get("module", "") or ""
        qualname = row.get("qualname", "") or ""

        return {
            "name": qualname,
            "path": f"src/{module.replace('.', '/')}.py" if module else "",
            "item_type": "symbol",
            "content": None,
            "signature": row.get("ast_signature", "") or "",
            "summary": row.get("intent", "") or "",
            "source": "database",
            "symbol_path": qualname,
            "metadata": {
                "symbol_id": str(row.get("id", "")),
                "kind": row.get("kind", "function"),
            },
        }
