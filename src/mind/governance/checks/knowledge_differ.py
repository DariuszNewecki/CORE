# src/mind/governance/checks/knowledge_differ.py
"""
A service to compare knowledge artifacts between a database source of truth
and legacy YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ID: 1ef15a86-5395-432d-8172-125773b55f0e
class KnowledgeDiffer:
    """Encapsulates the logic for diffing knowledge sources."""

    def __init__(self, session: AsyncSession, repo_root: Path):
        self.session = session
        self.repo_root = repo_root

    # ID: 353f2655-38da-4a43-9d61-2f28f8132493
    async def compare(self, config: dict[str, Any]) -> dict[str, Any]:
        """Compares DB to YAML for a given configuration."""
        yaml_path = self._resolve_yaml(*config["yaml_paths"])
        if not yaml_path:
            return {"status": "passed", "diff": None}

        schema, table = config["table"].split(".")
        db_rows, db_cols = await self._fetch_table(schema, table)
        yaml_items = self._read_yaml(yaml_path, config["yaml_key"])

        yaml_keys = {k for item in yaml_items for k in item}
        compare_fields = sorted(list(yaml_keys.intersection(db_cols)))

        diff = self._diff_records(
            yaml_items, db_rows, config["primary_key"], compare_fields
        )

        # A diff is "clean" if all its value lists are empty.
        is_clean = not any(diff.values())
        return {
            "status": "passed" if is_clean else "failed",
            "diff": diff if not is_clean else None,
            "yaml_path": yaml_path,
        }

    async def _fetch_table(
        self, schema: str, table: str
    ) -> tuple[list[dict], list[str]]:
        """Fetches all rows and column names from a database table."""
        cols_sql = text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
        )
        result = await self.session.execute(cols_sql, {"s": schema, "t": table})
        cols = [row[0] for row in result.fetchall()]
        if not cols:
            return [], []

        # --- THIS IS THE FIX ---
        # 1. Build the list of quoted column names safely.
        quoted_cols = ", ".join(f'"{c}"' for c in cols)
        # 2. Use the prepared string in the final SQL statement.
        rows_sql = text(f'SELECT {quoted_cols} FROM "{schema}"."{table}"')
        # --- END OF FIX ---

        rows = (await self.session.execute(rows_sql)).mappings().all()
        return [dict(row) for row in rows], cols

    def _resolve_yaml(self, *candidates: str) -> Path | None:
        """Finds the first existing YAML file from a list of candidates."""
        for rel_path in candidates:
            path = self.repo_root / rel_path
            if path.exists():
                return path
        return None

    def _read_yaml(self, path: Path, key: str) -> list[dict]:
        """Reads a YAML file and extracts items by key."""
        try:
            data = yaml.safe_load(path.read_text("utf-8")) or {}
            items = data.get(key, [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def _diff_records(
        self, yaml_items: list, db_items: list, p_key: str, fields: list
    ) -> dict:
        """Compares YAML and DB records and returns differences."""
        yaml_idx = {
            str(item.get(p_key)): item for item in yaml_items if item.get(p_key)
        }
        db_idx = {str(item.get(p_key)): item for item in db_items if item.get(p_key)}

        mismatched = []
        for key, yaml_rec in yaml_idx.items():
            db_rec = db_idx.get(key)
            if db_rec:
                field_diffs = {}
                for field in fields:
                    yaml_val = yaml_rec.get(field)
                    db_val = db_rec.get(field)
                    # Comparing as strings is a simple way to normalize None, '', etc.
                    if str(yaml_val or "") != str(db_val or ""):
                        field_diffs[field] = {"yaml": yaml_val, "db": db_val}
                if field_diffs:
                    mismatched.append({"key": key, "fields": field_diffs})

        return {
            "missing_in_db": sorted(list(set(yaml_idx.keys()) - set(db_idx.keys()))),
            "mismatched": mismatched,
        }
