# src/features/governance/checks/knowledge_source_check.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


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
    async def execute(
        self,
    ) -> CheckResult:  # <-- THIS METHOD WAS RENAMED FROM run() TO execute()
        yaml_paths = {
            "cli_registry": self._resolve_yaml(
                ".intent/mind/knowledge/cli_registry.yaml",
                ".intent/mind/knowledge/cli_registry.yml",
            ),
            "resource_manifest": self._resolve_yaml(
                ".intent/mind/knowledge/resource_manifest.yaml",
                ".intent/mind/knowledge/resource_manifest.yml",
            ),
            "cognitive_roles": self._resolve_yaml(
                ".intent/mind/knowledge/cognitive_roles.yaml",
                ".intent/mind/knowledge/cognitive_roles.yml",
            ),
        }

        # prepare structure for per-section outcomes
        section_results: Dict[str, Dict[str, Any]] = {}

        async with self.session_factory() as session:
            # Fetch rows + available columns for each table
            cli_rows, cli_cols = await self._fetch_table(
                session,
                "core",
                "cli_commands",
                preferred_order=["name", "module", "entrypoint", "enabled"],
            )
            llm_rows, llm_cols = await self._fetch_table(
                session,
                "core",
                "llm_resources",
                preferred_order=["name", "provider", "model", "enabled"],
            )
            roles_rows, roles_cols = await self._fetch_table(
                session,
                "core",
                "cognitive_roles",
                preferred_order=["name", "description", "enabled"],
            )

        # --- CLI registry
        section_results["cli_registry"] = await self._compare_section(
            label="cli_registry",
            yaml_path=yaml_paths["cli_registry"],
            db_rows=cli_rows,
            db_cols=cli_cols,
        )

        # --- LLM resources
        section_results["resource_manifest"] = await self._compare_section(
            label="resource_manifest",
            yaml_path=yaml_paths["resource_manifest"],
            db_rows=llm_rows,
            db_cols=llm_cols,
        )

        # --- Cognitive roles
        section_results["cognitive_roles"] = await self._compare_section(
            label="cognitive_roles",
            yaml_path=yaml_paths["cognitive_roles"],
            db_rows=roles_rows,
            db_cols=roles_cols,
        )

        # Determine pass/fail:
        # - If any section explicitly failed (has 'status' == 'failed'), overall fails.
        # - If require_yaml_exports=True and any section is 'skipped' due to missing YAML, overall fails.
        any_failed = any(v.get("status") == "failed" for v in section_results.values())
        if self.require_yaml_exports:
            any_skipped = any(
                v.get("status") == "skipped" for v in section_results.values()
            )
            passed = not any_failed and not any_skipped
        else:
            passed = not any_failed

        report = {
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
                    "cli_registry": "core.cli_commands",
                    "resource_manifest": "core.llm_resources",
                    "cognitive_roles": "core.cognitive_roles",
                },
            },
            "sections": section_results,
        }

        report_path = self.reports_dir / (
            datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json"
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return CheckResult(name=self.NAME, passed=passed, details=report)

    # ---------- Section comparator ----------
    async def _compare_section(
        self,
        *,
        label: str,
        yaml_path: Path | None,
        db_rows: List[Dict[str, Any]],
        db_cols: List[str],
    ) -> Dict[str, Any]:
        # Missing YAML
        if yaml_path is None:
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
            else:
                return {"status": "skipped", "reason": "yaml_missing", "diff": None}

        # YAML present → load and compare
        yaml_items = self._read_yaml(yaml_path)
        fields = self._fields_for_compare(yaml_items, db_cols)
        diff = self._diff_named_records(
            yaml_items, db_rows, key="name", compare_fields=fields
        )

        status = "passed" if self._diff_is_clean(diff) else "failed"
        return {
            "status": status,
            "yaml": str(yaml_path),
            "compare_fields": list(fields),
            "diff": diff,
        }

    # ---------- Helpers ----------
    def _resolve_yaml(self, *candidate_rel_paths: str) -> Path | None:
        for rel in candidate_rel_paths:
            p = self.repo_root / rel
            if p.exists():
                return p
        return None

    def _read_yaml(self, path: Path) -> List[Dict[str, Any]]:
        import yaml  # local import to avoid hard dep if unused

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        # Normalize to list-of-dicts
        if isinstance(data, dict):
            items = []
            for k, v in data.items():
                if isinstance(v, dict) and "name" not in v:
                    v["name"] = k
                items.append(v)
            return items
        if isinstance(data, list):
            return data
        return []

    async def _fetch_table(
        self,
        session: AsyncSession,
        schema: str,
        table: str,
        preferred_order: List[str],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        cols = await self._list_columns(session, schema, table)
        if not cols:
            return [], []

        select_cols = ", ".join([f'"{c}"' for c in cols])
        sql = text(f'SELECT {select_cols} FROM "{schema}"."{table}"')
        rows = (await session.execute(sql)).mappings().all()
        data = [dict(r) for r in rows]

        ordered_cols = [c for c in preferred_order if c in cols] + [
            c for c in cols if c not in preferred_order
        ]
        data = [{k: rec.get(k) for k in ordered_cols} for rec in data]
        return data, ordered_cols

    async def _list_columns(
        self, session: AsyncSession, schema: str, table: str
    ) -> List[str]:
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

    def _fields_for_compare(
        self, yaml_items: List[Dict[str, Any]], db_cols: List[str]
    ) -> Tuple[str, ...]:
        yaml_keys = set()
        for item in yaml_items:
            if isinstance(item, dict):
                yaml_keys.update(item.keys())

        keys = (yaml_keys & set(db_cols)) | {"name"}
        preferred = [
            "name",
            "module",
            "entrypoint",
            "provider",
            "model",
            "description",
            "enabled",
        ]
        ordered = [k for k in preferred if k in keys] + [
            k for k in sorted(keys) if k not in preferred
        ]
        return tuple(ordered)

    def _diff_named_records(
        self,
        yaml_items: List[Dict[str, Any]],
        db_items: List[Dict[str, Any]],
        key: str = "name",
        compare_fields: Tuple[str, ...] | None = None,
    ) -> Dict[str, Any]:
        compare_fields = compare_fields or self._union_keys(yaml_items, db_items)

        y_index = {
            str(i.get(key)).strip(): i for i in yaml_items if i.get(key) is not None
        }
        d_index = {
            str(i.get(key)).strip(): i for i in db_items if i.get(key) is not None
        }

        missing_in_db = sorted([k for k in y_index.keys() if k not in d_index])
        missing_in_yaml = sorted([k for k in d_index.keys() if k not in y_index])

        mismatched = []
        for k in sorted(set(y_index.keys()) & set(d_index.keys())):
            y = y_index[k]
            d = d_index[k]
            fields = {}
            for f in compare_fields:
                if f not in y and f not in d:
                    continue
                if y.get(f) != d.get(f):
                    fields[f] = {"yaml": y.get(f), "db": d.get(f)}
            if fields:
                mismatched.append({"name": k, "fields": fields})

        return {
            "missing_in_db": missing_in_db,
            "missing_in_yaml": missing_in_yaml,
            "mismatched": mismatched,
        }

    def _union_keys(
        self, a: List[Dict[str, Any]], b: List[Dict[str, Any]]
    ) -> Tuple[str, ...]:
        keys = set()
        for i in a + b:
            if isinstance(i, dict):
                keys.update(i.keys())
        preferred = [
            "name",
            "module",
            "entrypoint",
            "provider",
            "model",
            "description",
            "enabled",
        ]
        ordered = [k for k in preferred if k in keys] + [
            k for k in sorted(keys) if k not in preferred
        ]
        return tuple(ordered)

    def _diff_is_clean(self, diff: Dict[str, Any]) -> bool:
        return (
            not diff["missing_in_db"]
            and not diff["missing_in_yaml"]
            and not diff["mismatched"]
        )
