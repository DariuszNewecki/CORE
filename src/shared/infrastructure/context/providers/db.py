# src/shared/infrastructure/context/providers/db.py

"""
DBProvider - Fetches symbols from PostgreSQL.

CONSTITUTIONAL FIX (V2.3.8):
- Modularized to reduce Modularity Debt (50.6 -> ~34.0).
- Extracts SQL Generation to '_SQLRegistry'.
- Focuses purely on Database Retrieval.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select, text

from shared.infrastructure.database.models import Symbol
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
class _SQLRegistry:
    """Specialist in building complex SQL queries for the provider."""

    GRAPH_TRAVERSAL = text(
        """
        WITH RECURSIVE symbol_graph AS (
            SELECT id, qualname, calls, 0 as depth FROM core.symbols WHERE id = :symbol_id
            UNION ALL
            SELECT s.id, s.qualname, s.calls, sg.depth + 1
            FROM core.symbols s, symbol_graph sg
            WHERE sg.depth < :depth AND (
                s.qualname = ANY(SELECT jsonb_array_elements_text(sg.calls))
                OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(s.calls) AS elem WHERE elem ->> 0 = sg.qualname)
            )
        )
        SELECT s.* FROM core.symbols s
        JOIN (SELECT DISTINCT id FROM symbol_graph) AS ids ON s.id = ids.id
        WHERE s.id != :symbol_id;
    """
    )

    @staticmethod
    # ID: 9a58606a-051e-4a9e-9d1e-68306a246f32
    def build_module_pattern(path: str) -> str:
        pattern = (
            path.replace("src/", "").replace("/", ".").replace(".py", "").strip(".")
        )
        return f"{pattern}%" if pattern else "%"


# ID: cf20cce3-768d-4ab6-87e8-51f45928dd7e
class DBProvider:
    """Provides symbol data from database using DI session factory."""

    def __init__(self, session_factory: Callable | None = None):
        self._session_factory = session_factory

    # ID: 8a9b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
    async def fetch_symbols_for_scope(
        self, scope: dict[str, Any], max_items: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch symbols matching scope definition."""
        if not self._session_factory:
            return []

        includes = scope.get("include", [])
        # We use the specialist to build patterns
        patterns = [(_SQLRegistry.build_module_pattern(p), 1) for p in includes] or [
            ("%", 1)
        ]

        symbols = []
        async with self._session_factory() as db:
            for pattern, _ in patterns:
                stmt = (
                    select(Symbol)
                    .where(Symbol.is_public, Symbol.module.like(pattern))
                    .limit(max_items)
                )
                result = await db.execute(stmt)
                for row in result.scalars().all():
                    if len(symbols) >= max_items:
                        break
                    symbols.append(self._format_item(row))

        return symbols

    # ID: cbdd5c76-f03c-432e-accf-cc75d956eacc
    async def get_related_symbols(self, symbol_id: str, depth: int) -> list[dict]:
        """Fetch related symbols via recursive graph traversal."""
        if depth <= 0 or not self._session_factory:
            return []

        async with self._session_factory() as db:
            result = await db.execute(
                _SQLRegistry.GRAPH_TRAVERSAL, {"symbol_id": symbol_id, "depth": depth}
            )
            return [self._format_item(row) for row in result.mappings()]

    def _format_item(self, row: Any) -> dict:
        """Standardizes DB row into a Context Item."""
        return {
            "name": row.qualname,
            "path": f"src/{row.module.replace('.', '/')}.py",
            "item_type": "symbol",
            "signature": getattr(row, "ast_signature", "pending"),
            "summary": getattr(row, "intent", ""),
            "source": "db_query",
            "metadata": {
                "symbol_id": str(row.id),
                "kind": getattr(row, "kind", "function"),
            },
        }
