# src/body/cli/logic/governance/engine.py

"""
Governance Coverage Engine.
Determines system-wide compliance by cross-referencing the Constitution (Law)
with Enforcement Mappings (Implementation).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate import ASTGateEngine


def _extract_rules_from_policy(content: dict[str, Any]) -> list[dict[str, Any]]:
    rules = content.get("rules", [])
    return [r for r in rules if isinstance(r, dict)] if isinstance(rules, list) else []


def _detect_policy_format(content: dict[str, Any]) -> str:
    return (
        "flat"
        if "rules" in content and isinstance(content["rules"], list)
        else "unknown"
    )


def _canonical_policy_key(key: str, content: dict[str, Any]) -> str:
    source = (
        content.get("_source_path")
        or content.get("source_path")
        or content.get("__source_path")
    )
    if isinstance(source, str) and source.strip():
        return source
    declared_id = content.get("id") or content.get("policy_id")
    return declared_id if isinstance(declared_id, str) and declared_id.strip() else key


def _dedupe_loaded_resources(
    resources: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    seen, unique = set(), []
    for key, value in resources.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        unique.append((key, value))
    return sorted(unique, key=lambda kv: _canonical_policy_key(kv[0], kv[1]))


def _supported_ast_gate_check_types() -> set[str]:
    candidate = getattr(ASTGateEngine, "supported_check_types", None)
    if callable(candidate):
        try:
            res = candidate()
            return {str(x) for x in res if isinstance(x, str) and x.strip()}
        except Exception:
            return set()
    return set()


def _is_rule_implementable(engine: str | None, params: dict[str, Any]) -> bool:
    """
    V2.3 FIX: Logic moved to check the Engine and Parameters derived
    from the YAML Mappings, not the JSON Law.
    """
    if not engine:
        return False

    if engine == "ast_gate":
        check_type = params.get("check_type")
        if check_type is None:
            return True
        supported = _supported_ast_gate_check_types()
        # Ensure new types like 'required_calls' are recognized
        supported.add("id_anchor")
        supported.add("required_calls")
        return check_type in supported

    return engine in (
        "glob_gate",
        "workflow_gate",
        "knowledge_gate",
        "llm_gate",
        "regex_gate",
    )


def _load_executed_ids(evidence: dict[str, Any]) -> set[str]:
    for key in ["executed_rules", "executed_checks"]:
        ids = evidence.get(key)
        if isinstance(ids, list):
            return {x for x in ids if isinstance(x, str) and x.strip()}
    return set()


# ID: 48f98a6f-2010-43ae-96fb-1b54eb7ec657
def generate_coverage_map(repo_root: Path) -> dict[str, Any]:
    """
    Generates the coverage map by joining JSON Rules with YAML Mappings.
    """
    evidence_file = repo_root / "reports/audit/latest_audit.json"
    if not evidence_file.exists():
        executed_ids = set()
    else:
        with evidence_file.open(encoding="utf-8") as f:
            evidence = json.load(f)
        executed_ids = _load_executed_ids(evidence)

    # Initialize Context and the all-important Enforcement Loader
    auditor_context = AuditorContext(repo_root)
    mapping_loader = EnforcementMappingLoader(repo_root / ".intent")

    unique_docs = _dedupe_loaded_resources(auditor_context.policies or {})

    policy_metadata, all_rules = {}, []

    for key, content in unique_docs:
        policy_key = _canonical_policy_key(key, content)
        policy_metadata[policy_key] = {
            "title": str(content.get("title", "")),
            "id": str(content.get("id", "")),
            "format": _detect_policy_format(content),
        }

        for rule_dict in _extract_rules_from_policy(content):
            rid = rule_dict.get("id")
            if not rid or rid.startswith(("standard_", "schema_", "global_")):
                continue

            # NEW: Look up the implementation strategy from the YAML mappings
            strategy = mapping_loader.get_enforcement_strategy(rid)

            engine = strategy.get("engine") if strategy else None
            params = strategy.get("params", {}) if strategy else {}

            all_rules.append(
                {
                    "rule_id": rid,
                    "statement": rule_dict.get("statement")
                    or rule_dict.get("title")
                    or "",
                    "severity": str(rule_dict.get("enforcement") or "warning").lower(),
                    "policy": policy_key,
                    "check_engine": engine,
                    "implementable": _is_rule_implementable(engine, params),
                }
            )

    entries = []
    for rule in all_rules:
        in_exec = rule["rule_id"] in executed_ids

        status = "declared_only"
        if in_exec:
            status = "enforced"
        elif rule.get("implementable"):
            status = "implementable"

        entries.append(
            {"rule": rule, "coverage_status": status, "in_executed_ids": in_exec}
        )

    total = len(entries)
    enforced_count = sum(1 for e in entries if e["coverage_status"] == "enforced")
    implementable_count = sum(
        1 for e in entries if e["coverage_status"] == "implementable"
    )

    return {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "total_policy_rules": total,
            "total_executed_ids": len(executed_ids),
            "total_policy_files": len(policy_metadata),
        },
        "summary": {
            "rules_total": total,
            "rules_enforced": enforced_count,
            "rules_implementable": implementable_count,
            "rules_declared_only": total - enforced_count - implementable_count,
            "execution_rate": (
                round(100 * enforced_count / total, 1) if total > 0 else 0
            ),
        },
        "entries": entries,
        "executed_ids_list": sorted(executed_ids),
        "policy_metadata": policy_metadata,
    }


# ID: de089263-22f0-4548-996f-27bb2f4a2dd2
def ensure_coverage_map(repo_root: Path, file_handler: Any) -> Path:
    map_path = repo_root / "reports/governance/enforcement_coverage_map.json"

    # Force regeneration to reflect recent V2.3 mapping updates
    data = generate_coverage_map(repo_root)
    file_handler.write_runtime_json(str(map_path.relative_to(repo_root)), data)

    return map_path
