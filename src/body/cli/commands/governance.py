# src/body/cli/commands/governance.py
"""
Constitutional governance commands - enforcement coverage and verification.

UPDATED: Now supports BOTH old (nested sections) and new (flat rules array) formats.
This enables gradual migration to Big Boys pattern without breaking existing policies.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console

from shared.cli_utils import core_command
from shared.config import settings


console = Console()
governance_app = typer.Typer(
    help="Constitutional governance visibility and verification.", no_args_is_help=True
)


def _extract_rules_from_policy(content: dict) -> list[dict]:
    """
    Extract rules from policy content, supporting BOTH formats:
    - NEW: Flat "rules" array (Big Boys pattern - Kubernetes/AWS/OPA style)
    - OLD: Nested sections (backward compatibility)

    This dual support enables gradual migration without breaking existing policies.
    """
    rules_lists = []

    # === PRIMARY FORMAT: Flat "rules" array (PREFERRED) ===
    # This is the Kubernetes/AWS/OPA pattern - single source of enforcement rules
    if "rules" in content and isinstance(content["rules"], list):
        rules_lists.extend(content["rules"])

    # === LEGACY FORMATS: Nested sections (BACKWARD COMPATIBILITY) ===
    # Support during migration period - will be deprecated in v3.0.0
    legacy_sections = [
        "agent_rules",  # agent_governance.yaml
        "safety_rules",  # safety.yaml
        "style_rules",  # code_standards.yaml
        "capability_rules",  # code_standards.yaml
        "refactoring_rules",  # code_standards.yaml
        "module_size_limits",  # code_standards.yaml
        "file_header_rules",  # code_standards.yaml
        "import_structure_rules",  # code_standards.yaml
        "symbol_metadata_rules",  # code_standards.yaml
        "health_standards",  # code_standards.yaml
        "dependency_injection",  # code_standards.yaml
    ]

    for section_name in legacy_sections:
        if section_name in content and isinstance(content[section_name], list):
            rules_lists.extend(content[section_name])

    # === SPECIAL CASE: naming_conventions (nested dict) ===
    # Legacy format: naming_conventions.intent.*, naming_conventions.code.*
    if "naming_conventions" in content and isinstance(
        content["naming_conventions"], dict
    ):
        for category_name, category_rules in content["naming_conventions"].items():
            if isinstance(category_rules, list):
                rules_lists.extend(category_rules)

    return rules_lists


def _generate_coverage_map(repo_root: Path) -> dict:
    """
    Generate enforcement coverage map from audit evidence.

    Shows ALL policies, even those with only metadata IDs.
    Supports both old (nested) and new (flat) policy formats.

    Returns the coverage map dictionary.
    """
    evidence_file = repo_root / "reports/audit/latest_audit.json"
    charter_dir = repo_root / ".intent/charter"

    if not evidence_file.exists():
        raise FileNotFoundError(
            f"Audit evidence not found: {evidence_file}. "
            "Run 'core-admin check audit' first."
        )

    # Load audit evidence
    with evidence_file.open() as f:
        evidence = json.load(f)

    executed_checks = set(evidence.get("executed_checks", []))

    # Track ALL policy files (even those with only metadata)
    policy_metadata = {}  # policy_path -> {title, format}

    # Discover all constitutional rules
    all_rules = []
    for policy_file in charter_dir.rglob("*.yaml"):
        if policy_file.name.startswith("."):
            continue

        try:
            with policy_file.open(encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}

            policy_path = str(policy_file.relative_to(repo_root))

            # Detect format
            has_flat_rules = "rules" in content and isinstance(content["rules"], list)
            format_type = "flat" if has_flat_rules else "nested"

            # Store policy metadata
            policy_metadata[policy_path] = {
                "title": content.get("title", ""),
                "id": content.get("id", ""),
                "format": format_type,
            }

            # Extract rules using unified extractor
            rules_lists = _extract_rules_from_policy(content)

            for rule in rules_lists:
                if not isinstance(rule, dict):
                    continue

                rule_id = rule.get("id")
                if not rule_id:
                    continue

                # SKIP: Document-level metadata IDs (Big Boys pattern)
                # These are policy identifiers, not enforceable rules
                if rule_id.startswith(
                    ("standard_", "schema_", "constitution_", "global_")
                ):
                    continue

                # Get severity/enforcement
                severity = rule.get("severity") or rule.get("enforcement") or ""

                all_rules.append(
                    {
                        "rule_id": rule_id,
                        "statement": rule.get(
                            "statement", rule.get("title", rule.get("description", ""))
                        ),
                        "severity": str(severity).lower(),
                        "policy": policy_path,
                        "category": rule.get("category", "uncategorized"),
                    }
                )

        except Exception as e:
            console.print(
                f"[yellow]Warning: Failed to parse {policy_file}: {e}[/yellow]"
            )
            continue

    # Build coverage entries
    entries = []
    for rule in all_rules:
        rule_id = rule["rule_id"]
        status = "enforced" if rule_id in executed_checks else "declared_only"

        entries.append(
            {
                "rule": rule,
                "coverage_status": status,
                "in_executed_checks": rule_id in executed_checks,
            }
        )

    # Calculate summary
    total = len(entries)
    enforced = sum(1 for e in entries if e["coverage_status"] == "enforced")
    partial = 0  # Future enhancement
    declared = sum(1 for e in entries if e["coverage_status"] == "declared_only")

    # Count policies by format
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
            "rules_partially_enforced": partial,
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

    # Check if regeneration needed
    needs_regeneration = False

    if not coverage_map_path.exists():
        needs_regeneration = True
        reason = "Coverage map not found"
    elif not audit_evidence.exists():
        raise FileNotFoundError(
            f"Audit evidence not found: {audit_evidence}. "
            "Run 'core-admin check audit' first."
        )
    elif audit_evidence.stat().st_mtime > coverage_map_path.stat().st_mtime:
        needs_regeneration = True
        reason = "Audit is newer than coverage map"

    if needs_regeneration:
        console.print(f"[yellow]⚠ {reason}, regenerating...[/yellow]")

        # Generate coverage map
        coverage_data = _generate_coverage_map(repo_root)

        # Write to file
        coverage_map_path.parent.mkdir(parents=True, exist_ok=True)
        with coverage_map_path.open("w", encoding="utf-8") as f:
            json.dump(coverage_data, f, indent=2, ensure_ascii=False)

        console.print("[green]✅ Coverage map regenerated[/green]")

        # Show migration progress
        meta = coverage_data["metadata"]
        if meta.get("nested_format_policies", 0) > 0:
            console.print(
                f"[cyan]ℹ Migration progress: {meta.get('flat_format_policies', 0)} policies "
                f"using new format, {meta.get('nested_format_policies', 0)} still using legacy format[/cyan]"
            )

    return coverage_map_path


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
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

    Auto-regenerates coverage map if audit is newer (like kubectl, aws cli).
    Supports both old (nested) and new (flat) policy formats.

    Formats:
      - summary: Flat list of all rules (default)
      - hierarchical: Grouped by policy with enforcement rates
      - json: Machine-readable JSON output

    Examples:
        core-admin governance coverage
        core-admin governance coverage --format hierarchical
        core-admin governance coverage --format json --output coverage.json
    """
    repo_root = settings.REPO_PATH

    # Ensure coverage map is up-to-date (Big Boys pattern)
    coverage_map_path = _ensure_coverage_map(repo_root)

    # Load coverage data
    with coverage_map_path.open() as f:
        coverage_data = json.load(f)

    if format == "json":
        output_data = coverage_data
        if output:
            output.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print_json(data=output_data)

    elif format == "hierarchical":
        content = _render_hierarchical(coverage_data)
        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print(content)

    else:  # summary (default)
        content = _render_summary(coverage_data)
        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print(content)


def _render_summary(coverage_data: dict) -> str:
    """Render flat summary format."""
    entries = coverage_data.get("entries", [])
    summary = coverage_data.get("summary", {})
    metadata = coverage_data.get("metadata", {})

    enforced = [e for e in entries if e.get("coverage_status") == "enforced"]
    declared = [e for e in entries if e.get("coverage_status") == "declared_only"]

    lines = []
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

    # Sort gaps by severity
    gap_candidates = []
    for e in declared:
        rule = e.get("rule", {})
        sev = str(rule.get("severity", "")).lower()
        rid = rule.get("rule_id", "")
        pol = rule.get("policy", "")
        gap_candidates.append((sev, rid, pol))

    sev_rank = {"error": 0, "warn": 1, "warning": 1, "info": 2, "": 3}
    gap_candidates.sort(key=lambda x: (sev_rank.get(x[0], 9), x[1]))

    for sev, rid, pol in gap_candidates[:25]:
        sev_display = sev if sev else "unknown"
        lines.append(f"- **{sev_display}** `{rid}` — {pol}")
    lines.append("")

    return "\n".join(lines)


def _render_hierarchical(coverage_data: dict) -> str:
    """Render hierarchical format grouped by policy."""
    entries = coverage_data.get("entries", [])
    metadata = coverage_data.get("metadata", {})
    policy_metadata = coverage_data.get("policy_metadata", {})

    # Group by policy
    by_policy = defaultdict(list)
    for entry in entries:
        rule = entry.get("rule", {})
        policy = rule.get("policy", "unknown")
        by_policy[policy].append(entry)

    # Also include policies with NO enforceable rules (only metadata)
    for policy_path in policy_metadata.keys():
        if policy_path not in by_policy:
            by_policy[policy_path] = []  # Empty list = policy exists but no rules

    lines = []
    lines.append("# Enforcement Coverage by Policy")
    lines.append("")
    lines.append("Hierarchical view organized by policy file (like kubectl, aws cli).")
    lines.append("")
    lines.append(f"**Generated**: {metadata.get('generated_at_utc', 'unknown')}")
    lines.append("")

    # Summary stats
    total_policies = len(by_policy)
    fully_enforced = sum(
        1
        for p, r in by_policy.items()
        if r and all(e.get("coverage_status") == "enforced" for e in r)
    )
    partially_enforced = sum(
        1
        for p, r in by_policy.items()
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

    # Sort policies by enforcement rate (gaps first)
    policy_stats = []
    for policy, rules in by_policy.items():
        total = len(rules)
        enforced_count = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        rate = enforced_count / total if total > 0 else 0
        policy_format = policy_metadata.get(policy, {}).get("format", "unknown")
        policy_stats.append((policy, rules, total, enforced_count, rate, policy_format))

    policy_stats.sort(key=lambda x: (x[4], x[0]))

    lines.append("## Policies by Enforcement Rate (Gaps First)")
    lines.append("")

    for policy, rules, total, enforced_count, rate, policy_format in policy_stats:
        policy_short = "/".join(policy.split("/")[-3:]) if "/" in policy else policy
        status_icon = (
            "✅"
            if total > 0 and enforced_count == total
            else "⚠️"
            if enforced_count > 0
            else "❌"
        )
        format_badge = "🆕" if policy_format == "flat" else ""

        lines.append(f"### {status_icon} {policy_short} {format_badge}")
        lines.append(f"**Path**: `{policy}`  ")
        lines.append(
            f"**Enforcement**: {enforced_count}/{total} rules ({int(100 * rate)}%)"
        )
        if policy_format == "flat":
            lines.append("**Format**: New (flat rules array) ✨")
        lines.append("")

        if not rules:
            lines.append(
                "- _(Policy has only document metadata, no enforceable rules)_"
            )
            lines.append("")
            continue

        # Sort rules: gaps first
        rules_sorted = sorted(
            rules,
            key=lambda r: (
                r.get("coverage_status") == "enforced",
                r.get("rule", {}).get("rule_id", ""),
            ),
        )

        for rule_entry in rules_sorted[:20]:
            rule = rule_entry.get("rule", {})
            rule_id = rule.get("rule_id", "unknown")
            statement = rule.get("statement", "")[:100]
            if len(rule.get("statement", "")) > 100:
                statement += "..."
            status = rule_entry.get("coverage_status")
            severity = rule.get("severity", "")

            icon = "✅" if status == "enforced" else "❌"
            status_text = (
                "ENFORCED"
                if status == "enforced"
                else f"DECLARED ({severity})"
                if severity
                else "DECLARED"
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
    lines.append("- 🆕 **New format**: Using flat `rules` array (Big Boys pattern)")
    lines.append("")

    return "\n".join(lines)
