# src/will/tools/context/query_builder.py

"""
SQL query builder for symbol retrieval.
"""

from __future__ import annotations

from sqlalchemy import text


# ID: b4c13c27-9de5-4e0a-a65b-60cbec617ccd
class SymbolQueryBuilder:
    """Builds parameterized SQL queries for symbol retrieval."""

    @staticmethod
    # ID: efb3d7e9-3422-4364-8334-2747efce05cf
    def build_symbols_by_ids_query(
        symbol_ids: list[str],
    ) -> tuple[text, dict[str, str]]:
        """
        Build parameterized query to fetch symbols by IDs.

        Returns:
            Tuple of (SQLAlchemy text query, parameter dict)
        """
        if not symbol_ids:
            raise ValueError("symbol_ids cannot be empty")

        # Build parameter placeholders
        param_names = [f":id{i}" for i in range(len(symbol_ids))]
        placeholders = ", ".join(param_names)

        query_text = text(
            f"SELECT id, qualname, file_path, docstring, line_number "
            f"FROM core.symbols WHERE id IN ({placeholders})"
        )

        # Build parameter dict
        params = {f"id{i}": str(sid) for i, sid in enumerate(symbol_ids)}

        return query_text, params
