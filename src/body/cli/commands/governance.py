# src/body/cli/commands/governance.py
"""
Constitutional governance commands - enforcement coverage and verification.

Option A (SSOT, recommended):
- Coverage uses AuditorContext's loaded governance resources as the single source of truth.
- This avoids brittle filesystem scanning logic and automatically tracks PathResolver evolution.

Notes:
- AuditorContext indexes resources under multiple keys (e.g., stem, id, policy_id).
  Coverage deduplicates by object identity (same dict instance referenced multiple times).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from mind.governance.audit_context import AuditorContext
from shared.cli_utils import core_command
from shared.config import settings


console = Console()
governance_app = typer.Typer(
    help="Constitutional governance visibility and verification.", no_args_is_help=True
)


def _extract_rules_from_policy(content: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract rules from policy content, supporting BOTH formats:
    - NEW: Flat "rules" array (preferred)
    - OLD: Nested sections (backward compatibility)
    """
    rules: list[dict[str, Any]] = []

    # Primary format: flat rules list
    flat = content.get("rules")
    if isinstance(flat, list):
        for item in flat:
            if isinstance(item, dict):
                rules.append(item)

    # Legacy sections: lists of dict rules
    legacy_sections = [
        "agent_rules",
        "safety_rules",
        "style_rules",
        "capability_rules",
        "refactoring_rules",
        "module_size_limits",
        "file_header_rules",
        "import_structure_rules",
        "symbol_metadata_rules",
        "health_standards",
        "dependency_injection",
    ]
    for section_name in legacy_sections:
        section = content.get(section_name)
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict):
                    rules.append(item)

    # Special legacy: naming_conventions as nested dict-of-lists
    naming = content.get("naming_conventions")
    if isinstance(naming, dict):
        for _category_name, category_rules in naming.items():
            if isinstance(category_rules, list):
                for item in category_rules:
                    if isinstance(item, dict):
                        rules.append(item)

    return rules


def _detect_policy_format(content: dict[str, Any]) -> str:
    """
    Detect whether a policy uses flat or nested format.

    Returns: "flat", "nested", or "unknown"
    """
    rules_list = content.get("rules")
    if isinstance(rules_list, list) and rules_list:
        nested_indicators = {
            "allowed",
            "forbidden",
            "requirements",
            "pattern",
            "levels",
            "technique",
            "example",
            "definitions",
            "parameters",
            "allowed_actions",
            "benefits",
            "examples",
        }

        sample_size = min(3, len(rules_list))
        nested_count = 0

        flat_keys = {
            "id",
            "category",
            "statement",
            "enforcement",
            "cross_references",
            "rationale",
            "scope",
            "command",
            "metric",
            "severity",
            "title",
            "description",
        }

        for i in range(sample_size):
            rule = rules_list[i]
            if not isinstance(rule, dict):
                continue
            extra_keys = set(rule.keys()) - flat_keys
            if extra_keys & nested_indicators:
                nested_count += 1

        return "nested" if nested_count > (sample_size / 2) else "flat"

    legacy_indicators = [
        "agent_rules",
        "safety_rules",
        "style_rules",
        "capability_rules",
        "refactoring_rules",
        "module_size_limits",
        "file_header_rules",
        "import_structure_rules",
        "symbol_metadata_rules",
        "health_standards",
        "dependency_injection",
        "naming_conventions",
    ]
    if any(k in content for k in legacy_indicators):
        return "nested"

    return "unknown"


def _canonical_policy_key(key: str, content: dict[str, Any]) -> str:
    """
    Best-effort canonical identifier for a policy/standard resource for reporting.

    AuditorContext may not currently attach a source path into the dict; if it does
    in the future (recommended), we will prefer it automatically.
    """
    source = (
        content.get("_source_path")
        or content.get("source_path")
        or content.get("__source_path")
    )
    if isinstance(source, str) and source.strip():
        return source

    # If the dict itself declares an id, use it as the best stable key.
    declared_id = content.get("id") or content.get("policy_id")
    if isinstance(declared_id, str) and declared_id.strip():
        return declared_id

    # Fall back to the key used by AuditorContext (may be stem or id).
    return key


def _dedupe_loaded_resources(
    resources: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """
    AuditorContext indexes the same dict under multiple keys.
    Deduplicate by object identity (same dict instance).
    """
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

    # Stable ordering (use canonical key where possible)
    unique.sort(key=lambda kv: _canonical_policy_key(kv[0], kv[1]))
    return unique


def _generate_coverage_map(repo_root: Path) -> dict[str, Any]:
    """
    Generate enforcement coverage map from audit evidence.

    SSOT: AuditorContext-loaded governance resources.
    """
    evidence_file = repo_root / "reports/audit/latest_audit.json"
    if not evidence_file.exists():
        raise FileNotFoundError(
            f"Audit evidence not found: {evidence_file}. Run 'core-admin check audit' first."
        )

    with evidence_file.open(encoding="utf-8") as f:
        evidence = json.load(f)

    executed_checks = set(evidence.get("executed_checks", []))

    # Load governance resources via AuditorContext (SSOT interface)
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
            if not rule_id:
                continue

            # Skip document-level metadata IDs if you still have any such convention
            if isinstance(rule_id, str) and rule_id.startswith(
                ("standard_", "schema_", "constitution_", "global_")
            ):
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
                }
            )

    entries: list[dict[str, Any]] = []
    for rule in all_rules:
        rid = rule["rule_id"]
        status = "enforced" if rid in executed_checks else "declared_only"
        entries.append(
            {
                "rule": rule,
                "coverage_status": status,
                "in_executed_checks": rid in executed_checks,
            }
        )

    total = len(entries)
    enforced = sum(1 for e in entries if e["coverage_status"] == "enforced")
    declared = total - enforced

    flat_policies = sum(
        1 for m in policy_metadata.values() if m.get("format") == "flat"
    )
    nested_policies = sum(
        1 for m in policy_metadata.values() if m.get("format") == "nested"
    )

    return {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "evidence_file": str(evidence_file.relative_to(repo_root)),
            "total_executed_checks": len(executed_checks),
            "total_policy_files": len(policy_metadata),
            "flat_format_policies": flat_policies,
            "nested_format_policies": nested_policies,
        },
        "summary": {
            "rules_total": total,
            "rules_enforced": enforced,
            "rules_partially_enforced": 0,
            "rules_declared_only": declared,
            "enforcement_rate": round(100 * enforced / total, 1) if total > 0 else 0,
        },
        "entries": entries,
        "executed_checks_list": sorted(executed_checks),
        "policy_metadata": policy_metadata,
    }


def _ensure_coverage_map(repo_root: Path) -> Path:
    """
    Ensure coverage map exists and is up-to-date.

    Returns path to coverage map file.
    """
    audit_evidence = repo_root / "reports/audit/latest_audit.json"
    coverage_map_path = repo_root / "reports/governance/enforcement_coverage_map.json"

    needs_regeneration = False
    reason = ""

    if not coverage_map_path.exists():
        needs_regeneration = True
        reason = "Coverage map not found"
    elif not audit_evidence.exists():
        raise FileNotFoundError(
            f"Audit evidence not found: {audit_evidence}. Run 'core-admin check audit' first."
        )
    elif audit_evidence.stat().st_mtime > coverage_map_path.stat().st_mtime:
        needs_regeneration = True
        reason = "Audit is newer than coverage map"

    if needs_regeneration:
        console.print(f"[yellow]⚠ {reason}, regenerating...[/yellow]")

        coverage_data = _generate_coverage_map(repo_root)

        coverage_map_path.parent.mkdir(parents=True, exist_ok=True)
        with coverage_map_path.open("w", encoding="utf-8") as f:
            json.dump(coverage_data, f, indent=2, ensure_ascii=False)

        console.print("[green]✅ Coverage map regenerated[/green]")

        meta = coverage_data.get("metadata", {})
        if meta.get("nested_format_policies", 0) > 0:
            console.print(
                "[cyan]"
                f"INFO Migration progress: {meta.get('flat_format_policies', 0)} policies using new format, "
                f"{meta.get('nested_format_policies', 0)} still using legacy format"
                "[/cyan]"
            )

    return coverage_map_path


@governance_app.command("coverage")
@core_command(dangerous=False, requires_context=False)
# ID: 0753d0ea-9942-431f-b013-5ee5d09eb782
def enforcement_coverage(
    ctx: typer.Context,
    format: str = typer.Option(
        "summary",
        "--format",
        "-f",
        help="Output format: summary|hierarchical|json",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of console",
    ),
) -> None:
    """
    Show which constitutional rules are enforced vs declared.

    Auto-regenerates coverage map if audit is newer.
    Source of truth: AuditorContext-loaded governance resources.
    """
    repo_root = settings.REPO_PATH
    coverage_map_path = _ensure_coverage_map(repo_root)

    with coverage_map_path.open(encoding="utf-8") as f:
        coverage_data = json.load(f)

    if format == "json":
        if output:
            output.write_text(json.dumps(coverage_data, indent=2), encoding="utf-8")
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print_json(data=coverage_data)
        return

    if format == "hierarchical":
        content = _render_hierarchical(coverage_data)
    else:
        content = _render_summary(coverage_data)

    if output:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]✅ Written to {output}[/green]")
    else:
        console.print(content)


def _render_summary(coverage_data: dict[str, Any]) -> str:
    """Render flat summary format."""
    entries = coverage_data.get("entries", [])
    summary = coverage_data.get("summary", {})
    metadata = coverage_data.get("metadata", {})

    enforced = [e for e in entries if e.get("coverage_status") == "enforced"]
    declared = [e for e in entries if e.get("coverage_status") == "declared_only"]

    lines: list[str] = []
    lines.append("# Enforcement Coverage Summary")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total policies: {metadata.get('total_policy_files', 0)}")
    lines.append(
        f"  - New format (flat rules): {metadata.get('flat_format_policies', 0)}"
    )
    lines.append(
        f"  - Legacy format (nested): {metadata.get('nested_format_policies', 0)}"
    )
    lines.append(f"- Total rules: {summary.get('rules_total', 0)}")
    lines.append(f"- Enforced (evidence-backed): {summary.get('rules_enforced', 0)}")
    lines.append(f"- Declared only: {summary.get('rules_declared_only', 0)}")
    lines.append(f"- Enforcement rate: {summary.get('enforcement_rate', 0)}%")
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
        sev_display = sev if sev else "unknown"
        lines.append(f"- **{sev_display}** `{rid}` — {pol}")
    lines.append("")

    return "\n".join(lines)


def _render_hierarchical(coverage_data: dict[str, Any]) -> str:
    """Render hierarchical format grouped by policy."""
    entries = coverage_data.get("entries", [])
    metadata = coverage_data.get("metadata", {})
    policy_metadata = coverage_data.get("policy_metadata", {})

    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        rule = entry.get("rule", {})
        policy = rule.get("policy", "unknown")
        by_policy[str(policy)].append(entry)

    # Include policies with no rules (metadata-only docs)
    for policy_path in policy_metadata.keys():
        by_policy.setdefault(policy_path, [])

    lines: list[str] = []
    lines.append("# Enforcement Coverage by Policy")
    lines.append("")
    lines.append(
        "Hierarchical view organized by policy resource (SSOT = AuditorContext)."
    )
    lines.append("")
    lines.append(f"**Generated**: {metadata.get('generated_at_utc', 'unknown')}")
    lines.append("")

    total_policies = len(by_policy)
    fully_enforced = sum(
        1
        for _p, r in by_policy.items()
        if r and all(e.get("coverage_status") == "enforced" for e in r)
    )
    partially_enforced = sum(
        1
        for _p, r in by_policy.items()
        if r
        and any(e.get("coverage_status") == "enforced" for e in r)
        and not all(e.get("coverage_status") == "enforced" for e in r)
    )

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total policies**: {total_policies}")
    lines.append(
        f"  - New format (flat rules): {metadata.get('flat_format_policies', 0)}"
    )
    lines.append(
        f"  - Legacy format (nested): {metadata.get('nested_format_policies', 0)}"
    )
    lines.append(
        f"- **Fully enforced**: {fully_enforced} ({100 * fully_enforced // max(total_policies, 1)}%)"
    )
    lines.append(f"- **Partially enforced**: {partially_enforced}")
    lines.append(
        f"- **Not enforced**: {total_policies - fully_enforced - partially_enforced}"
    )
    lines.append("")

    policy_stats: list[tuple[str, list[dict[str, Any]], int, int, float, str]] = []
    for policy, rules in by_policy.items():
        total = len(rules)
        enforced_count = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        rate = enforced_count / total if total > 0 else 0.0
        policy_format = policy_metadata.get(policy, {}).get("format", "unknown")
        policy_stats.append((policy, rules, total, enforced_count, rate, policy_format))

    # Gaps first
    policy_stats.sort(key=lambda x: (x[4], x[0]))

    lines.append("## Policies by Enforcement Rate (Gaps First)")
    lines.append("")

    for policy, rules, total, enforced_count, rate, policy_format in policy_stats:
        policy_short = "/".join(policy.split("/")[-3:]) if "/" in policy else policy
        status_icon = (
            "✅"
            if total > 0 and enforced_count == total
            else ("⚠️" if enforced_count > 0 else "❌")
        )
        format_badge = "🆕" if policy_format == "flat" else ""

        lines.append(f"### {status_icon} {policy_short} {format_badge}")
        lines.append(f"**Policy**: `{policy}`  ")
        lines.append(
            f"**Enforcement**: {enforced_count}/{total} rules ({int(100 * rate)}%)"
        )
        if policy_format == "flat":
            lines.append("**Format**: New (flat rules array)")
        lines.append("")

        if not rules:
            lines.append(
                "- _(Policy has no extractable enforceable rules under current parser)_"
            )
            lines.append("")
            continue

        rules_sorted = sorted(
            rules,
            key=lambda r: (
                r.get("coverage_status") != "enforced",
                str(r.get("rule", {}).get("rule_id", "")),
            ),
        )

        for rule_entry in rules_sorted[:20]:
            rule = rule_entry.get("rule", {})
            rule_id = rule.get("rule_id", "unknown")
            statement_full = rule.get("statement", "") or ""
            statement = statement_full[:100] + (
                "..." if len(statement_full) > 100 else ""
            )
            status = rule_entry.get("coverage_status")
            severity = rule.get("severity", "")

            icon = "✅" if status == "enforced" else "❌"
            status_text = (
                "ENFORCED"
                if status == "enforced"
                else (f"DECLARED ({severity})" if severity else "DECLARED")
            )
            lines.append(f"- {icon} **`{rule_id}`**: {statement} _{status_text}_")

        if len(rules_sorted) > 20:
            lines.append(f"- _...and {len(rules_sorted) - 20} more rules_")
        lines.append("")

    lines.append("---")
    lines.append("## Legend")
    lines.append("")
    lines.append("- ✅ **ENFORCED**: Active check with audit evidence")
    lines.append("- ❌ **DECLARED**: Written but not checked")
    lines.append("- 🆕 **New format**: Using flat `rules` array")
    lines.append("")

    return "\n".join(lines)
