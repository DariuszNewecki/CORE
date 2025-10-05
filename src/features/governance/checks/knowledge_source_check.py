"""
Compares DB single-source-of-truth tables with their (legacy) YAML exports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# Configuration
TABLE_CONFIGS = {
    "cli_registry": {
        "yaml_paths": [
            ".intent/mind/knowledge/cli_registry.yaml",
            ".intent/mind/knowledge/cli_registry.yml",
        ],
        "table": "core.cli_commands",
        "yaml_key": "commands",
        "primary_key": "name",
        "preferred_order": ["name", "module", "entrypoint", "enabled"],
    },
    "resource_manifest": {
        "yaml_paths": [
            ".intent/mind/knowledge/resource_manifest.yaml",
            ".intent/mind/knowledge/resource_manifest.yml",
        ],
        "table": "core.llm_resources",
        "yaml_key": "llm_resources",
        "primary_key": "name",
        "preferred_order": ["name", "provider", "model", "enabled"],
    },
    "cognitive_roles": {
        "yaml_paths": [
            ".intent/mind/knowledge/cognitive_roles.yaml",
            ".intent/mind/knowledge/cognitive_roles.yml",
        ],
        "table": "core.cognitive_roles",
        "yaml_key": "cognitive_roles",
        "primary_key": "role",
        "preferred_order": ["name", "description", "enabled"],
    },
}

FIELD_PRIORITY = [
    "name",
    "role",
    "module",
    "entrypoint",
    "provider",
    "model",
    "description",
    "enabled",
]


@dataclass
# ID: 55de1540-39da-4a5d-9e40-b0614cfe655f
class CheckResult:
    name: str
    passed: bool
    details: Dict[str, Any]


# ID: 81d6e8ed-a6f6-444c-acda-9064896c5111
class KnowledgeSourceCheck:
    """
    Compares DB single-source-of-truth tables with their (legacy) YAML exports under:
      .intent/mind/knowledge/{cli_registry, resource_manifest, cognitive_roles}.yaml

    Behavior:
      - If a YAML file is missing and `require_yaml_exports=False` (default), that section is SKIPPED.
      - If a YAML file exists, it is compared with the DB rows (adaptive to actual DB columns).
      - Any drift in an existing YAML file FAILS the check.

    Set `require_yaml_exports=True` to enforce the presence of YAML exports.
    """

    NAME = "knowledge_source_check"

    def __init__(
        self,
        repo_root: Path,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        reports_dir: Path | None = None,
        require_yaml_exports: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.engine = engine
        self.session_factory = session_factory
        self.reports_dir = reports_dir or repo_root / "reports" / "knowledge_ssot"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.require_yaml_exports = require_yaml_exports

    # ---------- Public API ----------
    # ID: b846d3ab-5762-4bc8-9dfc-f3fa060da29c
    async def execute(self) -> CheckResult:
        """Execute the knowledge source check and return results."""
        # Resolve YAML paths
        yaml_paths = {
            section: self._resolve_yaml(*config["yaml_paths"])
            for section, config in TABLE_CONFIGS.items()
        }

        # Fetch all database tables
        section_results = {}
        async with self.session_factory() as session:
            for section, config in TABLE_CONFIGS.items():
                schema, table = config["table"].split(".")
                db_rows, db_cols = await self._fetch_table(
                    session, schema, table, config["preferred_order"]
                )

                section_results[section] = await self._compare_section(
                    label=section,
                    yaml_path=yaml_paths[section],
                    db_rows=db_rows,
                    db_cols=db_cols,
                    yaml_key=config["yaml_key"],
                    primary_key=config["primary_key"],
                )

        # Determine overall pass/fail status
        passed = self._determine_overall_status(section_results)

        # Build and save report
        report = self._build_report(passed, yaml_paths, section_results)
        self._save_report(report)

        return CheckResult(name=self.NAME, passed=passed, details=report)

    # ---------- Section comparison ----------
    async def _compare_section(
        self,
        *,
        label: str,
        yaml_path: Path | None,
        db_rows: List[Dict[str, Any]],
        db_cols: List[str],
        yaml_key: str,
        primary_key: str,
    ) -> Dict[str, Any]:
        """Compare a single section (YAML vs DB)."""
        # Handle missing YAML file
        if yaml_path is None:
            return self._handle_missing_yaml()

        # Load and compare
        yaml_items = self._read_yaml(yaml_path, yaml_key)
        compare_fields = self._determine_compare_fields(yaml_items, db_cols)
        diff = self._diff_records(yaml_items, db_rows, primary_key, compare_fields)

        status = "passed" if self._is_diff_clean(diff) else "failed"
        return {
            "status": status,
            "yaml": str(yaml_path),
            "compare_fields": list(compare_fields),
            "diff": diff,
        }

    def _handle_missing_yaml(self) -> Dict[str, Any]:
        """Handle the case where a YAML file is missing."""
        if self.require_yaml_exports:
            return {
                "status": "failed",
                "reason": "yaml_missing_and_required",
                "diff": {
                    "missing_in_db": [],
                    "missing_in_yaml": [],
                    "mismatched": [],
                },
            }
        return {"status": "skipped", "reason": "yaml_missing", "diff": None}

    # ---------- Database operations ----------
    async def _fetch_table(
        self,
        session: AsyncSession,
        schema: str,
        table: str,
        preferred_order: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Fetch all rows and columns from a database table."""
        cols = await self._list_columns(session, schema, table)
        if not cols:
            return [], []

        # Query the table
        select_cols = ", ".join([f'"{c}"' for c in cols])
        sql = text(f'SELECT {select_cols} FROM "{schema}"."{table}"')
        rows = (await session.execute(sql)).mappings().all()

        # Order columns consistently
        ordered_cols = self._order_columns(cols, preferred_order)
        data = [{k: dict(r).get(k) for k in ordered_cols} for r in rows]

        return data, ordered_cols

    async def _list_columns(
        self, session: AsyncSession, schema: str, table: str
    ) -> List[str]:
        """Get the list of columns for a table from information_schema."""
        sql = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
            """
        )
        rows = (
            await session.execute(sql, {"schema": schema, "table": table})
        ).mappings()
        return [r["column_name"] for r in rows]

    # ---------- YAML operations ----------
    def _resolve_yaml(self, *candidate_rel_paths: str) -> Path | None:
        """Find the first existing YAML file from a list of candidates."""
        for rel in candidate_rel_paths:
            p = self.repo_root / rel
            if p.exists():
                return p
        return None

    def _read_yaml(self, path: Path, key: str) -> List[Dict[str, Any]]:
        """Read a YAML file and extract items by key."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                return []

            items = data.get(key, [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    # ---------- Comparison logic ----------
    def _determine_compare_fields(
        self, yaml_items: List[Dict[str, Any]], db_cols: List[str]
    ) -> Tuple[str, ...]:
        """Determine which fields to compare based on YAML and DB columns."""
        yaml_keys = set()
        for item in yaml_items:
            if isinstance(item, dict):
                yaml_keys.update(item.keys())

        # Include primary key possibilities
        common_keys = (yaml_keys & set(db_cols)) | {"name", "role"}
        return self._order_fields(common_keys)

    def _diff_records(
        self,
        yaml_items: List[Dict[str, Any]],
        db_items: List[Dict[str, Any]],
        primary_key: str,
        compare_fields: Tuple[str, ...],
    ) -> Dict[str, Any]:
        """Compare YAML and DB records and return differences."""
        # Build indexes by primary key
        yaml_index = self._build_index(yaml_items, primary_key)
        db_index = self._build_index(db_items, primary_key)

        # Find missing records
        missing_in_db = sorted(set(yaml_index.keys()) - set(db_index.keys()))
        missing_in_yaml = sorted(set(db_index.keys()) - set(yaml_index.keys()))

        # Find mismatched records
        mismatched = self._find_mismatches(yaml_index, db_index, compare_fields)

        return {
            "missing_in_db": missing_in_db,
            "missing_in_yaml": missing_in_yaml,
            "mismatched": mismatched,
        }

    def _build_index(
        self, items: List[Dict[str, Any]], key: str
    ) -> Dict[str, Dict[str, Any]]:
        """Build an index of items by their primary key."""
        return {
            str(item.get(key)).strip(): item
            for item in items
            if isinstance(item, dict) and item.get(key) is not None
        }

    def _find_mismatches(
        self,
        yaml_index: Dict[str, Dict[str, Any]],
        db_index: Dict[str, Dict[str, Any]],
        compare_fields: Tuple[str, ...],
    ) -> List[Dict[str, Any]]:
        """Find records that exist in both but have different field values."""
        mismatched = []
        common_keys = set(yaml_index.keys()) & set(db_index.keys())

        for key in sorted(common_keys):
            yaml_record = yaml_index[key]
            db_record = db_index[key]

            field_diffs = self._compare_records(yaml_record, db_record, compare_fields)

            if field_diffs:
                mismatched.append({"name": key, "fields": field_diffs})

        return mismatched

    def _compare_records(
        self,
        yaml_record: Dict[str, Any],
        db_record: Dict[str, Any],
        compare_fields: Tuple[str, ...],
    ) -> Dict[str, Dict[str, Any]]:
        """Compare two records field by field."""
        diffs = {}

        for field in compare_fields:
            # Skip fields not present in either record
            if field not in yaml_record and field not in db_record:
                continue

            yaml_val = yaml_record.get(field)
            db_val = db_record.get(field)

            # Normalize: treat empty strings and None as equivalent
            if self._values_equivalent(yaml_val, db_val):
                continue

            if yaml_val != db_val:
                diffs[field] = {"yaml": yaml_val, "db": db_val}

        return diffs

    @staticmethod
    def _values_equivalent(val1: Any, val2: Any) -> bool:
        """Check if two values are equivalent (treating None and empty string as same)."""
        return (val1 is None or val1 == "") and (val2 is None or val2 == "")

    @staticmethod
    def _is_diff_clean(diff: Dict[str, Any]) -> bool:
        """Check if a diff shows no differences."""
        return (
            not diff["missing_in_db"]
            and not diff["missing_in_yaml"]
            and not diff["mismatched"]
        )

    # ---------- Utility functions ----------
    @staticmethod
    def _order_columns(cols: List[str], preferred: List[str]) -> List[str]:
        """Order columns with preferred ones first, rest alphabetically."""
        return [c for c in preferred if c in cols] + [
            c for c in cols if c not in preferred
        ]

    @staticmethod
    def _order_fields(fields: set) -> Tuple[str, ...]:
        """Order fields with priority fields first, rest alphabetically."""
        ordered = [f for f in FIELD_PRIORITY if f in fields] + [
            f for f in sorted(fields) if f not in FIELD_PRIORITY
        ]
        return tuple(ordered)

    def _determine_overall_status(
        self, section_results: Dict[str, Dict[str, Any]]
    ) -> bool:
        """Determine if the overall check passed based on section results."""
        any_failed = any(
            result.get("status") == "failed" for result in section_results.values()
        )

        if self.require_yaml_exports:
            any_skipped = any(
                result.get("status") == "skipped" for result in section_results.values()
            )
            return not any_failed and not any_skipped

        return not any_failed

    def _build_report(
        self,
        passed: bool,
        yaml_paths: Dict[str, Path | None],
        section_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the complete report structure."""
        return {
            "check": self.NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "passed": passed,
            "require_yaml_exports": self.require_yaml_exports,
            "sources": {
                "yaml_paths": {
                    k: str(v) if isinstance(v, Path) else None
                    for k, v in yaml_paths.items()
                },
                "db_tables": {
                    section: config["table"]
                    for section, config in TABLE_CONFIGS.items()
                },
            },
            "sections": section_results,
        }

    def _save_report(self, report: Dict[str, Any]) -> None:
        """Save the report to a timestamped JSON file."""
        report_path = self.reports_dir / (
            datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json"
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
