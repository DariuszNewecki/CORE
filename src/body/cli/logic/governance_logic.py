# src/body/cli/logic/governance_logic.py
"""
Engine logic for constitutional governance reporting.
Handles coverage map generation, rule extraction, and markdown rendering.

CONSTITUTIONAL FIX:
- Zero-Loss Modularization: All logic preserved exactly from governance.py.
- Headless: No Typer or UI dependencies.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.logic.engines.ast_gate import ASTGateEngine


# ID: 64b1509a-d090-4e54-9afb-545edec329db
def get_coverage_data(repo_root: Path, file_handler: Any) -> dict[str, Any]:
    """Authoritative entry point to get coverage data."""
    map_path = _ensure_coverage_map(repo_root, file_handler)
    with map_path.open(encoding="utf-8") as f:
        return json.load(f)


def _extract_rules_from_policy(content: dict[str, Any]) -> list[dict[str, Any]]:
    rules = content.get("rules", [])
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]


def _detect_policy_format(content: dict[str, Any]) -> str:
    if "rules" in content and isinstance(content["rules"], list):
        return "flat"
    return "unknown"


def _canonical_policy_key(key: str, content: dict[str, Any]) -> str:
    source = (
        content.get("_source_path")
        or content.get("source_path")
        or content.get("__source_path")
    )
    if isinstance(source, str) and source.strip():
        return source
    declared_id = content.get("id") or content.get("policy_id")
    if isinstance(declared_id, str) and declared_id.strip():
        return declared_id
    return key


def _dedupe_loaded_resources(
    resources: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    seen: set[int] = set()
    unique: list[tuple[str, dict[str, Any]]] = []
    for key, value in resources.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        oid = id(value)
        if oid in seen:
            continue
        seen.add(oid)
        unique.append((key, value))
    unique.sort(key=lambda kv: _canonical_policy_key(kv[0], kv[1]))
    return unique


def _rule_check_engine(rule: dict[str, Any]) -> str | None:
    check = rule.get("check")
    if not isinstance(check, dict):
        return None
    engine = check.get("engine")
    return engine if isinstance(engine, str) and engine.strip() else None


def _rule_check_params(rule: dict[str, Any]) -> dict[str, Any]:
    check = rule.get("check")
    if not isinstance(check, dict):
        return {}
    params = check.get("params")
    return params if isinstance(params, dict) else {}


def _supported_ast_gate_check_types() -> set[str]:
    candidate = getattr(ASTGateEngine, "supported_check_types", None)
    if callable(candidate):
        try:
            result = candidate()
            if isinstance(result, (set, list, tuple)):
                return {str(x) for x in result if isinstance(x, str) and x.strip()}
        except Exception:
            return set()
    return set()


def _is_rule_implementable(rule: dict[str, Any]) -> bool:
    engine = _rule_check_engine(rule)
    if not engine:
        return False
    params = _rule_check_params(rule)
    if engine == "ast_gate":
        check_type = params.get("check_type")
        if check_type is None:
            return True
        supported = _supported_ast_gate_check_types()
        supported.add("id_anchor")
        return check_type in supported
    if engine in ("glob_gate", "workflow_gate", "knowledge_gate", "llm_gate"):
        return True
    return False


def _load_executed_ids(evidence: dict[str, Any]) -> set[str]:
    executed = evidence.get("executed_rules")
    if isinstance(executed, list):
        return {x for x in executed if isinstance(x, str) and x.strip()}
    executed = evidence.get("executed_checks", [])
    if isinstance(executed, list):
        return {x for x in executed if isinstance(x, str) and x.strip()}
    return set()


def _generate_coverage_map(repo_root: Path) -> dict[str, Any]:
    evidence_file = repo_root / "reports/audit/latest_audit.json"
    if not evidence_file.exists():
        raise FileNotFoundError(f"Audit evidence not found: {evidence_file}")

    with evidence_file.open(encoding="utf-8") as f:
        evidence = json.load(f)

    executed_ids = _load_executed_ids(evidence)
    auditor_context = AuditorContext(repo_root)
    resources = auditor_context.policies or {}
    unique_docs = _dedupe_loaded_resources(resources)

    policy_metadata: dict[str, dict[str, Any]] = {}
    all_rules: list[dict[str, Any]] = []

    for key, content in unique_docs:
        policy_key = _canonical_policy_key(key, content)
        format_type = _detect_policy_format(content)

        policy_metadata[policy_key] = {
            "title": (
                content.get("title", "")
                if isinstance(content.get("title"), str)
                else ""
            ),
            "id": content.get("id", "") if isinstance(content.get("id"), str) else "",
            "format": format_type,
        }

        for rule in _extract_rules_from_policy(content):
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id.strip():
                continue
            if rule_id.startswith(("standard_", "schema_", "constitution_", "global_")):
                continue

            severity = rule.get("severity") or rule.get("enforcement") or ""
            statement = (
                rule.get("statement")
                or rule.get("title")
                or rule.get("description")
                or ""
            )

            all_rules.append(
                {
                    "rule_id": rule_id,
                    "statement": statement,
                    "severity": str(severity).lower(),
                    "policy": policy_key,
                    "category": rule.get("category", "uncategorized"),
                    "check_engine": _rule_check_engine(rule),
                    "check_type": _rule_check_params(rule).get("check_type"),
                    "implementable": _is_rule_implementable(rule),
                }
            )

    entries: list[dict[str, Any]] = []
    for rule in all_rules:
        rid = rule["rule_id"]
        in_exec = rid in executed_ids
        if in_exec:
            status = "enforced"
        elif rule.get("implementable", False):
            status = "implementable"
        else:
            status = "declared_only"

        entries.append(
            {
                "rule": rule,
                "coverage_status": status,
                "in_executed_ids": in_exec,
            }
        )

    total = len(entries)
    return {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "evidence_file": str(evidence_file.relative_to(repo_root)),
            "evidence_key_used": (
                "executed_rules"
                if isinstance(evidence.get("executed_rules"), list)
                else "executed_checks"
            ),
            "total_executed_ids": len(executed_ids),
            "total_policy_files": len(policy_metadata),
            "flat_format_policies": sum(
                1 for m in policy_metadata.values() if m["format"] == "flat"
            ),
            "nested_format_policies": sum(
                1 for m in policy_metadata.values() if m["format"] == "nested"
            ),
        },
        "summary": {
            "rules_total": total,
            "rules_enforced": sum(
                1 for e in entries if e["coverage_status"] == "enforced"
            ),
            "rules_implementable": sum(
                1 for e in entries if e["coverage_status"] == "implementable"
            ),
            "rules_declared_only": sum(
                1 for e in entries if e["coverage_status"] == "declared_only"
            ),
            "execution_rate": (
                round(
                    100
                    * sum(1 for e in entries if e["coverage_status"] == "enforced")
                    / total,
                    1,
                )
                if total > 0
                else 0
            ),
        },
        "entries": entries,
        "executed_ids_list": sorted(executed_ids),
        "policy_metadata": policy_metadata,
    }


def _ensure_coverage_map(repo_root: Path, file_handler: Any) -> Path:
    audit_evidence = repo_root / "reports/audit/latest_audit.json"
    coverage_map_path = repo_root / "reports/governance/enforcement_coverage_map.json"

    needs_regeneration = not coverage_map_path.exists() or (
        audit_evidence.exists()
        and audit_evidence.stat().st_mtime > coverage_map_path.stat().st_mtime
    )

    if needs_regeneration:
        coverage_data = _generate_coverage_map(repo_root)
        rel_path = str(coverage_map_path.relative_to(repo_root))
        file_handler.write_runtime_json(rel_path, coverage_data)

    return coverage_map_path


# ID: b55ed7d9-1347-4efa-8c01-c80a82ba9cbf
def render_summary(coverage_data: dict[str, Any]) -> str:
    """Literal restoration of original summary rendering."""
    entries = coverage_data.get("entries", [])
    summary = coverage_data.get("summary", {})
    metadata = coverage_data.get("metadata", {})

    enforced = [e for e in entries if e.get("coverage_status") == "enforced"]
    implementable = [e for e in entries if e.get("coverage_status") == "implementable"]
    declared = [e for e in entries if e.get("coverage_status") == "declared_only"]

    lines: list[str] = []
    lines.append("# Enforcement Coverage Summary")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total rules: {summary.get('rules_total', 0)}")
    lines.append(f"- Enforced (executed): {summary.get('rules_enforced', 0)}")
    lines.append(
        f"- Implementable (not executed): {summary.get('rules_implementable', 0)}"
    )
    lines.append(
        f"- Declared only (not implementable): {summary.get('rules_declared_only', 0)}"
    )
    lines.append(f"- Execution rate: {summary.get('execution_rate', 0)}%")
    lines.append("")
    lines.append(
        f"**Evidence key used**: `{metadata.get('evidence_key_used', 'unknown')}`"
    )
    lines.append("")

    lines.append("## Enforced rules")
    lines.append("")
    if not enforced:
        lines.append("_None yet._")
    else:
        for e in sorted(enforced, key=lambda x: x.get("rule", {}).get("rule_id", "")):
            rule = e.get("rule", {})
            lines.append(f"- `{rule.get('rule_id')}` — {rule.get('policy')}")
    lines.append("")

    lines.append("## Top gaps (highest severity first)")
    lines.append("")

    gap_candidates: list[tuple[str, str, str]] = []
    for e in declared:
        rule = e.get("rule", {})
        sev = str(rule.get("severity", "")).lower()
        rid = str(rule.get("rule_id", ""))
        pol = str(rule.get("policy", ""))
        gap_candidates.append((sev, rid, pol))

    sev_rank = {"error": 0, "warn": 1, "warning": 1, "info": 2, "": 3}
    gap_candidates.sort(key=lambda x: (sev_rank.get(x[0], 9), x[1]))

    for sev, rid, pol in gap_candidates[:25]:
        lines.append(f"- **{sev or 'unknown'}** `{rid}` — {pol}")
    lines.append("")

    return "\n".join(lines)


# ID: 119560f4-f97e-4926-a5e8-7b5e2755870f
def render_hierarchical(coverage_data: dict[str, Any]) -> str:
    """Literal restoration of original hierarchical rendering."""
    entries = coverage_data.get("entries", [])
    metadata = coverage_data.get("metadata", {})
    policy_metadata = coverage_data.get("policy_metadata", {})

    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        rule = entry.get("rule", {})
        policy = rule.get("policy", "unknown")
        by_policy[str(policy)].append(entry)

    lines: list[str] = []
    lines.append("# Enforcement Coverage by Policy")
    lines.append("")
    lines.append(f"**Generated**: {metadata.get('generated_at_utc', 'unknown')}")
    lines.append("")

    total_policies = len(by_policy)
    lines.append("## Summary")
    lines.append(f"- **Total policies**: {total_policies}")
    lines.append("")

    policy_stats = []
    for policy, rules in by_policy.items():
        total = len(rules)
        executed_count = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        rate = executed_count / total if total > 0 else 0.0
        policy_stats.append((policy, rules, total, executed_count, rate))

    policy_stats.sort(key=lambda x: (x[4], x[0]))

    for policy, rules, total, executed_count, rate in policy_stats:
        status_icon = (
            "✅"
            if total > 0 and executed_count == total
            else ("⚠️" if executed_count > 0 else "❌")
        )
        lines.append(f"### {status_icon} {policy}")
        lines.append(
            f"**Executed**: {executed_count}/{total} rules ({int(100 * rate)}%)"
        )
        lines.append("")

        for rule_entry in sorted(
            rules, key=lambda r: r.get("rule", {}).get("rule_id", "")
        ):
            rule = rule_entry.get("rule", {})
            rid = rule.get("rule_id", "unknown")
            stmt = rule.get("statement", "")[:100] + "..."
            status = rule_entry.get("coverage_status")

            if status == "enforced":
                icon = "✅"
            elif status == "implementable":
                icon = "🟦"
            else:
                icon = "❌"

            lines.append(f"- {icon} **`{rid}`**: {stmt}")
        lines.append("")

    lines.append("---\n## Legend")
    lines.append("- ✅ **EXECUTED**: Rule was executed in latest audit evidence")
    lines.append("- 🟦 **IMPLEMENTABLE**: Engine exists but audit did not execute it")
    lines.append("- ❌ **DECLARED**: Rule exists but is not implementable")

    return "\n".join(lines)
