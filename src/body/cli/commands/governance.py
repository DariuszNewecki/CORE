# src/body/cli/commands/governance.py
"""
Constitutional governance commands - enforcement coverage and verification.

Coverage model (robust):
- enforced: rule was executed in the latest audit evidence (executed_rules preferred; fallback: executed_checks)
- implementable: rule declares a check engine and (if applicable) a check_type
  that the engine can execute, but the latest audit did not execute it
- declared_only: rule exists but is not implementable (unknown engine/check_type)

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
from mind.logic.engines.ast_gate import ASTGateEngine
from shared.cli_utils import core_command
from shared.config import settings


console = Console()
governance_app = typer.Typer(
    help="Constitutional governance visibility and verification.", no_args_is_help=True
)


def _extract_rules_from_policy(content: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract rules from policy content (v2 flat format).

    All policies migrated to v2 format (confirmed 2024-12-28).
    Legacy format support removed - see policy_format_migration.py for migration tool.
    """
    rules = content.get("rules", [])
    if not isinstance(rules, list):
        return []

    # Filter to valid rule dicts only
    return [r for r in rules if isinstance(r, dict)]


def _detect_policy_format(content: dict[str, Any]) -> str:
    """
    Detect policy format (all policies use v2 flat format as of 2024-12-28).

    Returns 'flat' if rules array present, 'unknown' otherwise.
    Legacy nested format detection removed - all policies migrated.
    """
    if "rules" in content and isinstance(content["rules"], list):
        return "flat"
    return "unknown"


def _canonical_policy_key(key: str, content: dict[str, Any]) -> str:
    """Best-effort canonical identifier for a policy/standard resource for reporting."""
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
    """Deduplicate AuditorContext resources by object identity."""
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
    """
    Best-effort discovery of ASTGate check types.

    Robustness rule:
    - Coverage must not hard-fail if ASTGateEngine does not expose a capability list.
    """
    candidate = getattr(ASTGateEngine, "supported_check_types", None)
    if callable(candidate):
        try:
            result = candidate()
            if isinstance(result, (set, list, tuple)):
                return {str(x) for x in result if isinstance(x, str) and x.strip()}
        except Exception:
            return set()

    # If ASTGate doesn't expose this, treat only 'None' check_type as implementable.
    return set()


def _is_rule_implementable(rule: dict[str, Any]) -> bool:
    """
    Determine whether a rule is implementable given current runtime engines.
    Updated to recognize all CORE engines (Glob, Workflow, Knowledge, etc).
    """
    engine = _rule_check_engine(rule)
    if not engine:
        return False

    params = _rule_check_params(rule)

    # 1. AST Gate Intelligence
    if engine == "ast_gate":
        check_type = params.get("check_type")
        if check_type is None:
            return True
        supported = _supported_ast_gate_check_types()
        # Include the alias we just added to the engine
        supported.add("id_anchor")
        return check_type in supported

    # 2. Glob Gate Intelligence (Always implementable if engine is present)
    if engine == "glob_gate":
        return True

    # 3. Workflow Gate Intelligence (Always implementable)
    if engine == "workflow_gate":
        return True

    # 4. Knowledge Gate Intelligence (Always implementable)
    if engine == "knowledge_gate":
        return True

    # 5. LLM Gate (Implementable by definition)
    if engine == "llm_gate":
        return True

    return False


def _load_executed_ids(evidence: dict[str, Any]) -> set[str]:
    """
    Load executed IDs from evidence in a forward-compatible way.

    Rule:
    - Prefer executed_rules (authoritative rule-level coverage)
    - Fallback to executed_checks (legacy)
    """
    executed = evidence.get("executed_rules")
    if isinstance(executed, list):
        return {x for x in executed if isinstance(x, str) and x.strip()}

    executed = evidence.get("executed_checks", [])
    if isinstance(executed, list):
        return {x for x in executed if isinstance(x, str) and x.strip()}

    return set()


def _generate_coverage_map(repo_root: Path) -> dict[str, Any]:
    """Generate enforcement coverage map from audit evidence (SSOT = AuditorContext)."""
    evidence_file = repo_root / "reports/audit/latest_audit.json"
    if not evidence_file.exists():
        raise FileNotFoundError(
            f"Audit evidence not found: {evidence_file}. Run 'core-admin check audit' first."
        )

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

            engine = _rule_check_engine(rule)
            params = _rule_check_params(rule)
            check_type = (
                params.get("check_type")
                if isinstance(params.get("check_type"), str)
                else None
            )

            all_rules.append(
                {
                    "rule_id": rule_id,
                    "statement": statement,
                    "severity": str(severity).lower(),
                    "policy": policy_key,
                    "category": rule.get("category", "uncategorized"),
                    "check_engine": engine,
                    "check_type": check_type,
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
    enforced = sum(1 for e in entries if e["coverage_status"] == "enforced")
    implementable = sum(1 for e in entries if e["coverage_status"] == "implementable")
    declared = sum(1 for e in entries if e["coverage_status"] == "declared_only")

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
            "evidence_key_used": (
                "executed_rules"
                if isinstance(evidence.get("executed_rules"), list)
                else "executed_checks"
            ),
            "total_executed_ids": len(executed_ids),
            "total_policy_files": len(policy_metadata),
            "flat_format_policies": flat_policies,
            "nested_format_policies": nested_policies,
        },
        "summary": {
            "rules_total": total,
            "rules_enforced": enforced,
            "rules_implementable": implementable,
            "rules_declared_only": declared,
            "execution_rate": round(100 * enforced / total, 1) if total > 0 else 0,
            "implementable_rate": (
                round(100 * (enforced + implementable) / total, 1) if total > 0 else 0
            ),
        },
        "entries": entries,
        "executed_ids_list": sorted(executed_ids),
        "policy_metadata": policy_metadata,
    }


def _ensure_coverage_map(repo_root: Path) -> Path:
    """Ensure coverage map exists and is up-to-date."""
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
    Show which constitutional rules are enforced vs implementable vs declared-only.

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

    content = (
        _render_hierarchical(coverage_data)
        if format == "hierarchical"
        else _render_summary(coverage_data)
    )

    if output:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]✅ Written to {output}[/green]")
    else:
        console.print(content)


def _render_summary(coverage_data: dict[str, Any]) -> str:
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
    lines.append(f"- Total policies: {metadata.get('total_policy_files', 0)}")
    lines.append(
        f"  - New format (flat rules): {metadata.get('flat_format_policies', 0)}"
    )
    lines.append(
        f"  - Legacy format (nested): {metadata.get('nested_format_policies', 0)}"
    )
    lines.append(f"- Total rules: {summary.get('rules_total', 0)}")
    lines.append(f"- Enforced (executed): {summary.get('rules_enforced', 0)}")
    lines.append(
        f"- Implementable (not executed): {summary.get('rules_implementable', 0)}"
    )
    lines.append(
        f"- Declared only (not implementable): {summary.get('rules_declared_only', 0)}"
    )
    lines.append(f"- Execution rate: {summary.get('execution_rate', 0)}%")
    lines.append(f"- Implementable rate: {summary.get('implementable_rate', 0)}%")
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

    lines.append("## Implementable but not executed")
    lines.append("")
    if not implementable:
        lines.append("_None._")
    else:
        for e in sorted(
            implementable, key=lambda x: x.get("rule", {}).get("rule_id", "")
        ):
            rule = e.get("rule", {})
            engine = rule.get("check_engine") or "unknown"
            ctype = rule.get("check_type")
            ctype_part = f", check_type={ctype}" if ctype else ""
            lines.append(
                f"- `{rule.get('rule_id')}` — {rule.get('policy')} (engine={engine}{ctype_part})"
            )
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
    entries = coverage_data.get("entries", [])
    metadata = coverage_data.get("metadata", {})
    policy_metadata = coverage_data.get("policy_metadata", {})

    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        rule = entry.get("rule", {})
        policy = rule.get("policy", "unknown")
        by_policy[str(policy)].append(entry)

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
    lines.append(
        f"**Evidence key used**: `{metadata.get('evidence_key_used', 'unknown')}`"
    )
    lines.append("")

    total_policies = len(by_policy)
    fully_executed = sum(
        1
        for _p, r in by_policy.items()
        if r and all(e.get("coverage_status") == "enforced" for e in r)
    )
    partially_executed = sum(
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
    lines.append(f"- **Fully executed**: {fully_executed}")
    lines.append(f"- **Partially executed**: {partially_executed}")
    lines.append(
        f"- **Not executed**: {total_policies - fully_executed - partially_executed}"
    )
    lines.append("")

    policy_stats: list[tuple[str, list[dict[str, Any]], int, int, float, str]] = []
    for policy, rules in by_policy.items():
        total = len(rules)
        executed_count = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        rate = executed_count / total if total > 0 else 0.0
        policy_format = policy_metadata.get(policy, {}).get("format", "unknown")
        policy_stats.append((policy, rules, total, executed_count, rate, policy_format))

    policy_stats.sort(key=lambda x: (x[4], x[0]))

    lines.append("## Policies by Execution Rate (Gaps First)")
    lines.append("")

    for policy, rules, total, executed_count, rate, policy_format in policy_stats:
        policy_short = "/".join(policy.split("/")[-3:]) if "/" in policy else policy
        status_icon = (
            "✅"
            if total > 0 and executed_count == total
            else ("⚠️" if executed_count > 0 else "❌")
        )
        format_badge = "🆕" if policy_format == "flat" else ""

        lines.append(f"### {status_icon} {policy_short} {format_badge}")
        lines.append(f"**Policy**: `{policy}`  ")
        lines.append(
            f"**Executed**: {executed_count}/{total} rules ({int(100 * rate)}%)"
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

            if status == "enforced":
                icon = "✅"
                status_text = "EXECUTED"
            elif status == "implementable":
                icon = "🟦"
                status_text = (
                    f"IMPLEMENTABLE ({severity})" if severity else "IMPLEMENTABLE"
                )
            else:
                icon = "❌"
                status_text = f"DECLARED ({severity})" if severity else "DECLARED"

            lines.append(f"- {icon} **`{rule_id}`**: {statement} _{status_text}_")

        if len(rules_sorted) > 20:
            lines.append(f"- _...and {len(rules_sorted) - 20} more rules_")
        lines.append("")

    lines.append("---")
    lines.append("## Legend")
    lines.append("")
    lines.append("- ✅ **EXECUTED**: Rule was executed in latest audit evidence")
    lines.append(
        "- 🟦 **IMPLEMENTABLE**: Engine/check_type exists but audit did not execute it"
    )
    lines.append(
        "- ❌ **DECLARED**: Rule exists but is not implementable by current engines"
    )
    lines.append("- 🆕 **New format**: Using flat `rules` array")
    lines.append("")

    return "\n".join(lines)
