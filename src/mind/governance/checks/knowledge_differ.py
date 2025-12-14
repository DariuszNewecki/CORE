# src/mind/governance/checks/knowledge_differ.py
"""
A service to compare knowledge artifacts between a database source of truth
and legacy YAML files.
Ref: standard_data_governance (Knowledge Integrity)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1ef15a86-5395-432d-8172-125773b55f0e
class KnowledgeDiffer:
    """
    Encapsulates the logic for diffing knowledge sources.
    Compares DB tables (SSOT) against YAML mirrors.
    """

    def __init__(self, session: AsyncSession, repo_root: Path):
        self.session = session
        self.repo_root = repo_root

    # ID: 353f2655-38da-4a43-9d61-2f28f8132493
    async def compare(self, config: dict[str, Any]) -> dict[str, Any]:
        """Compares DB to YAML for a given configuration."""
        yaml_path = self._resolve_yaml(*config["yaml_paths"])
        if not yaml_path:
            # If the file doesn't exist, we can't compare.
            # Depending on policy, this might be okay or an error.
            # Assuming 'missing mirror' is handled by other checks (FileChecks).
            return {"status": "passed", "diff": None}

        schema, table = config["table"].split(".")

        # 1. Fetch DB Data
        try:
            db_rows, db_cols = await self._fetch_table(schema, table)
        except Exception as e:
            logger.error("Failed to fetch table %s.%s: %s", schema, table, e)
            return {"status": "error", "error": f"DB Read Failed: {e}"}

        # 2. Read YAML Data
        yaml_items = self._read_yaml(yaml_path, config["yaml_key"])
        if yaml_items is None:
            # Fail-safe: Do not pass if YAML is unreadable
            return {"status": "error", "error": f"YAML Read Failed: {yaml_path}"}

        # 3. Determine Common Fields
        yaml_keys = {k for item in yaml_items for k in item}
        compare_fields = sorted(list(yaml_keys.intersection(db_cols)))

        if not compare_fields:
            # If no common fields, we can't diff.
            logger.warning(
                "No common fields found between %s and %s.%s", yaml_path, schema, table
            )
            return {"status": "passed", "diff": None}  # Or warning?

        # 4. Perform Diff
        diff = self._diff_records(
            yaml_items, db_rows, config["primary_key"], compare_fields
        )

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
        # Note: raw SQL is used here for dynamic introspection of information_schema.
        # Inputs schema/table come from internal config, not user input.

        cols_sql = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t "
            "ORDER BY ordinal_position"
        )
        result = await self.session.execute(cols_sql, {"s": schema, "t": table})
        cols = [row[0] for row in result.fetchall()]

        if not cols:
            return [], []

        # Safe column quoting
        quoted_cols = ", ".join(f'"{c}"' for c in cols)

        # Validate schema/table names to prevent injection (Defense in Depth)
        if not (schema.isidentifier() and table.isidentifier()):
            raise ValueError(f"Invalid schema or table name: {schema}.{table}")

        rows_sql = text(f'SELECT {quoted_cols} FROM "{schema}"."{table}"')
        rows = (await self.session.execute(rows_sql)).mappings().all()

        return [dict(row) for row in rows], cols

    def _resolve_yaml(self, *candidates: str) -> Path | None:
        """Finds the first existing YAML file from a list of candidates."""
        for rel_path in candidates:
            path = self.repo_root / rel_path
            if path.exists():
                return path
        return None

    def _read_yaml(self, path: Path, key: str) -> list[dict] | None:
        """
        Reads a YAML file and extracts items by key.
        Returns None on failure to prevent silent passes.
        """
        try:
            content = path.read_text("utf-8")
            data = yaml.safe_load(content) or {}
            items = data.get(key, [])
            if not isinstance(items, list):
                logger.error("YAML key '%s' in %s is not a list", key, path)
                return None
            return items
        except Exception as e:
            logger.error("Failed to parse YAML %s: %s", path, e)
            return None

    def _diff_records(
        self, yaml_items: list, db_items: list, p_key: str, fields: list
    ) -> dict:
        """Compares YAML and DB records and returns differences."""
        # Convert to string keys for robust comparison
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

                    # Normalize for comparison (None vs "" vs 0)
                    v1 = str(yaml_val) if yaml_val is not None else ""
                    v2 = str(db_val) if db_val is not None else ""

                    if v1 != v2:
                        field_diffs[field] = {"yaml": yaml_val, "db": db_val}

                if field_diffs:
                    mismatched.append({"key": key, "fields": field_diffs})

        missing_in_db = sorted(list(set(yaml_idx.keys()) - set(db_idx.keys())))

        # We generally don't check "missing in YAML" because YAML is a mirror
        # and might be a subset, but depending on strictness we could add it.

        return {
            "missing_in_db": missing_in_db,
            "mismatched": mismatched,
        }
