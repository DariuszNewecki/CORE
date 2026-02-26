#!/usr/bin/env python3
"""
Enforcement Coverage Map Generator — Operational MVP (Readable Summary)

This generator produces a truthful, auditable enforcement coverage map.

It performs, in one deterministic pass:
1) Discover declared "rule-like" objects anywhere under .intent/charter/**/*.yaml
2) Apply explicit enforcement links from reports/governance/audit_rule_links.yaml (optional)
3) Apply direct audit evidence from reports/audit/latest_audit.json (no inference)
4) Upgrade to 'enforced' only when evidence exists
5) Write canonical artifacts and time-bucketed history snapshot
6) Produce a human-readable summary with:
   - enforced rule list
   - top gaps
   - coverage by policy file

Key principle:
- Never over-claim enforcement.
- Evidence beats inference.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

INTENT_CHARTER_DIR = REPO_ROOT / ".intent" / "charter"

GOVERNANCE_DIR = REPO_ROOT / "reports" / "governance"
HISTORY_DIR = GOVERNANCE_DIR / "history"

AUDIT_DIR = REPO_ROOT / "reports" / "audit"
AUDIT_EVIDENCE = AUDIT_DIR / "latest_audit.json"

CANONICAL_YAML = GOVERNANCE_DIR / "enforcement_coverage_map.yaml"
CANONICAL_JSON = GOVERNANCE_DIR / "enforcement_coverage_map.json"
CANONICAL_SUMMARY = GOVERNANCE_DIR / "enforcement_coverage_summary.md"

AUDIT_RULE_LINKS = GOVERNANCE_DIR / "audit_rule_links.yaml"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_dir() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%SZ")


def _git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _iter_yaml_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.yaml")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Rule discovery (broad but conservative)
# ---------------------------------------------------------------------------

_RULE_TEXT_KEYS = ("statement", "description", "rationale", "title")


def _looks_rule_like(obj: dict[str, Any]) -> bool:
    """
    Conservative heuristic:
    - must have string 'id'
    - must have at least one descriptive text field OR an 'enforcement'/'severity' field
    """
    rule_id = obj.get("id")
    if not (isinstance(rule_id, str) and rule_id.strip()):
        return False

    has_text = any(
        isinstance(obj.get(k), str) and obj.get(k).strip() for k in _RULE_TEXT_KEYS
    )
    has_enforcement = "enforcement" in obj or "severity" in obj
    return has_text or has_enforcement


def _extract_rule(obj: dict[str, Any], policy_path: str) -> dict[str, Any]:
    rule_id = str(obj.get("id")).strip()

    statement = ""
    for k in _RULE_TEXT_KEYS:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            statement = v.strip()
            break

    severity = obj.get("enforcement") if "enforcement" in obj else obj.get("severity")

    return {
        "policy_path": policy_path,
        "rule_id": rule_id,
        "statement": statement,
        "severity": severity,
    }


def _walk(obj: Any, policy_path: str, out: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if _looks_rule_like(obj):
            out.append(_extract_rule(obj, policy_path))
        for v in obj.values():
            _walk(v, policy_path, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, policy_path, out)


def _extract_all_declared_rules() -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []

    for yaml_file in _iter_yaml_files(INTENT_CHARTER_DIR):
        data = _load_yaml(yaml_file)
        policy_path = str(yaml_file.relative_to(REPO_ROOT))
        _walk(data, policy_path, discovered)

    # Deduplicate by (policy_path, rule_id)
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for r in discovered:
        key = (r["policy_path"], r["rule_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    return unique


# ---------------------------------------------------------------------------
# Evidence + links
# ---------------------------------------------------------------------------


def _load_executed_checks() -> set[str]:
    if not AUDIT_EVIDENCE.exists():
        return set()

    payload = _load_json(AUDIT_EVIDENCE)
    executed = payload.get("executed_checks", [])
    if not isinstance(executed, list):
        return set()

    out: set[str] = set()
    for item in executed:
        if isinstance(item, str) and item.strip():
            out.add(item.strip())
    return out


def _load_links() -> list[dict[str, Any]]:
    data = _load_yaml(AUDIT_RULE_LINKS)
    links = data.get("links", [])
    if not isinstance(links, list):
        return []
    return [l for line in links if isinstance(l, dict)]


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------


def _norm_severity(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return "unknown"


def _render_summary(
    *,
    entries: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    enforced = [e for e in entries if e.get("coverage_status") == "enforced"]
    partial = [e for e in entries if e.get("coverage_status") == "partially_enforced"]
    declared = [e for e in entries if e.get("coverage_status") == "declared_only"]

    # Coverage by policy file
    by_policy = defaultdict(lambda: Counter())
    for e in entries:
        rule = e.get("rule", {})
        policy = rule.get("policy", "unknown")
        status = e.get("coverage_status", "unknown")
        by_policy[policy][status] += 1

    # Top gaps: error-level declared-only (fallback to unknown severity)
    gap_candidates: list[tuple[str, str, str]] = []
    for e in declared:
        rule = e.get("rule", {})
        sev = _norm_severity(rule.get("severity"))
        rid = str(rule.get("rule_id", ""))
        pol = str(rule.get("policy", ""))
        # Prefer meaningful IDs
        if rid:
            gap_candidates.append((sev, rid, pol))

    # Sort gaps: error first, then warn, then info, then unknown; within that by rule_id
    sev_rank = {"error": 0, "warn": 1, "warning": 1, "info": 2, "unknown": 3}
    gap_candidates.sort(key=lambda x: (sev_rank.get(x[0], 9), x[1]))

    top_gaps = gap_candidates[:25]

    # Enforced list (sorted)
    enforced_list: list[tuple[str, str]] = []
    for e in enforced:
        rule = e.get("rule", {})
        rid = str(rule.get("rule_id", ""))
        pol = str(rule.get("policy", ""))
        if rid:
            enforced_list.append((rid, pol))
    enforced_list.sort()

    # Build markdown
    lines: list[str] = []
    lines.append("# Enforcement Coverage Summary")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total rules: {summary.get('rules_total', 0)}")
    lines.append(f"- Enforced (evidence-backed): {summary.get('rules_enforced', 0)}")
    lines.append(
        f"- Partially enforced (declared link only): {summary.get('rules_partially_enforced', 0)}"
    )
    lines.append(f"- Declared only: {summary.get('rules_declared_only', 0)}")
    lines.append(f"- Unknown: {summary.get('rules_unknown', 0)}")
    lines.append("")

    lines.append("## Evidence")
    lines.append("")
    lines.append(
        f"- Evidence file present: {'yes' if AUDIT_EVIDENCE.exists() else 'no'}"
    )
    if AUDIT_EVIDENCE.exists():
        lines.append(f"- Evidence path: {str(AUDIT_EVIDENCE.relative_to(REPO_ROOT))}")
    lines.append("")

    lines.append("## Enforced rules (evidence-backed)")
    lines.append("")
    if not enforced_list:
        lines.append("_None yet._")
    else:
        for rid, pol in enforced_list:
            lines.append(f"- `{rid}` — {pol}")
    lines.append("")

    lines.append("## Top gaps (declared-only, highest severity first)")
    lines.append("")
    if not top_gaps:
        lines.append("_No gaps detected (unexpected for MVP)._")
    else:
        for sev, rid, pol in top_gaps:
            lines.append(f"- **{sev}** `{rid}` — {pol}")
    lines.append("")

    lines.append("## Coverage by policy file")
    lines.append("")
    lines.append("| Policy | Enforced | Partial | Declared only | Unknown |")
    lines.append("|---|---:|---:|---:|---:|")
    for policy in sorted(by_policy.keys()):
        c = by_policy[policy]
        lines.append(
            f"| {policy} | {c.get('enforced', 0)} | {c.get('partially_enforced', 0)} | "
            f"{c.get('declared_only', 0)} | {c.get('unknown', 0)} |"
        )
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- A rule is marked **enforced** only when direct audit evidence exists (rule id in `executed_checks`)."
    )
    lines.append(
        "- Declared links in `audit_rule_links.yaml` can mark rules as **partially_enforced** without upgrading to **enforced**."
    )
    lines.append(
        "- This report is intentionally conservative: it prefers under-claiming to over-claiming."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------


def generate() -> None:
    map_data = _load_yaml(CANONICAL_YAML)
    if not isinstance(map_data, dict):
        map_data = {}

    map_data.setdefault("id", "enforcement_coverage_map")
    map_data.setdefault("version", "0.1.0")
    map_data.setdefault("status", "mvp")
    map_data.setdefault("scope", "repository")

    # Metadata
    map_data.setdefault("metadata", {})
    map_data["metadata"]["generated_at_utc"] = _utc_now()
    map_data["metadata"]["generated_by"] = "generate_enforcement_coverage_map.py"
    repo_meta = map_data["metadata"].setdefault("repository", {})
    repo_meta.setdefault("name", "CORE")
    repo_meta["commit"] = _git_commit()

    # Discover rules
    declared_rules = _extract_all_declared_rules()

    # Base entries
    entries: list[dict[str, Any]] = []
    for rule in declared_rules:
        entries.append(
            {
                "rule": {
                    "policy": rule["policy_path"],
                    "rule_id": rule["rule_id"],
                    "statement": rule["statement"],
                    "severity": rule.get("severity"),
                },
                "enforcement": [],
                "coverage_status": "declared_only",
                "notes": "Rule discovered in constitution; no enforcement linked yet.",
            }
        )

    # Load links and evidence
    links = _load_links()
    executed_checks = _load_executed_checks()

    links_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for line in links:
        policy = line.get("policy")
        rule_id = line.get("rule_id")
        enforcement = line.get("enforcement")
        if not (
            isinstance(policy, str)
            and isinstance(rule_id, str)
            and isinstance(enforcement, dict)
        ):
            continue
        links_index.setdefault((policy, rule_id), []).append(enforcement)

    for entry in entries:
        rule = entry["rule"]
        policy = rule["policy"]
        rule_id = rule["rule_id"]

        linked = links_index.get((policy, rule_id), [])
        if linked:
            entry["enforcement"] = linked
            entry["coverage_status"] = "partially_enforced"
            entry["notes"] = "Linked via explicit audit-rule declaration."

        # Direct evidence: audit system reports this rule/check id executed
        if rule_id in executed_checks:
            if not entry["enforcement"]:
                entry["enforcement"] = [
                    {
                        "mechanism_id": "audit_checks",
                        "check_id": rule_id,
                        "mode": "static_scan",
                        "strength": rule.get("severity") or "unknown",
                        "evidence": str(AUDIT_EVIDENCE.relative_to(REPO_ROOT)),
                    }
                ]
            else:
                for e in entry["enforcement"]:
                    if isinstance(e, dict) and "evidence" not in e:
                        e["evidence"] = str(AUDIT_EVIDENCE.relative_to(REPO_ROOT))
            entry["coverage_status"] = "enforced"
            entry["notes"] = (
                "Enforced by direct audit evidence (id present in executed_checks)."
            )

    map_data["entries"] = entries

    enforced_count = sum(1 for e in entries if e.get("coverage_status") == "enforced")
    partial_count = sum(
        1 for e in entries if e.get("coverage_status") == "partially_enforced"
    )
    declared_only_count = sum(
        1 for e in entries if e.get("coverage_status") == "declared_only"
    )
    unknown_count = sum(1 for e in entries if e.get("coverage_status") == "unknown")

    summary = map_data.setdefault("summary", {})
    summary["rules_total"] = len(entries)
    summary["rules_enforced"] = enforced_count
    summary["rules_partially_enforced"] = partial_count
    summary["rules_declared_only"] = declared_only_count
    summary["rules_unknown"] = unknown_count

    GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    _write_yaml(CANONICAL_YAML, map_data)
    _write_json(CANONICAL_JSON, map_data)

    CANONICAL_SUMMARY.write_text(
        _render_summary(entries=entries, summary=summary),
        encoding="utf-8",
    )

    snapshot_dir = HISTORY_DIR / _timestamp_dir()
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    shutil.copy2(CANONICAL_YAML, snapshot_dir / CANONICAL_YAML.name)
    shutil.copy2(CANONICAL_JSON, snapshot_dir / CANONICAL_JSON.name)
    shutil.copy2(CANONICAL_SUMMARY, snapshot_dir / CANONICAL_SUMMARY.name)

    print("[OK] Enforcement Coverage Map generated (declared + evidence-backed)")
    print(f" - Rules discovered: {summary['rules_total']}")
    print(f" - Enforced rules: {summary['rules_enforced']}")
    print(f" - Snapshot: {snapshot_dir}")


if __name__ == "__main__":
    generate()
