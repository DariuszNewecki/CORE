#!/usr/bin/env python3
"""
Generate hierarchical enforcement coverage summary grouped by policy.

Produces a readable markdown report showing:
- Each policy file
- Rules within that policy
- Status of each rule (enforced/declared)
- Aggregate statistics per policy

Usage:
    python scripts/generate_hierarchical_coverage_summary.py
"""

import json
from collections import defaultdict
from pathlib import Path


def load_json(path):
    """Load JSON file safely."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_hierarchical_summary(repo_root: Path):
    """Generate hierarchical summary grouped by policy."""

    coverage_map = repo_root / "reports/governance/enforcement_coverage_map.json"
    output_path = repo_root / "reports/governance/enforcement_coverage_by_policy.md"

    # Load coverage data
    coverage_data = load_json(coverage_map)
    entries = coverage_data.get("entries", [])

    # Group by policy
    by_policy = defaultdict(list)
    for entry in entries:
        rule = entry.get("rule", {})
        policy = rule.get("policy", "unknown")
        by_policy[policy].append(entry)

    # Build markdown
    lines = []
    lines.append("# Enforcement Coverage by Policy")
    lines.append("")
    lines.append(
        "Hierarchical view of constitutional enforcement organized by policy file."
    )
    lines.append("")
    lines.append(
        f"**Generated**: {coverage_data.get('metadata', {}).get('generated_at_utc', 'unknown')}"
    )
    lines.append("")

    # Summary stats
    total_policies = len(by_policy)
    fully_enforced_policies = 0
    partially_enforced_policies = 0

    for policy, rules in by_policy.items():
        enforced = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        if enforced == len(rules):
            fully_enforced_policies += 1
        elif enforced > 0:
            partially_enforced_policies += 1

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total policies**: {total_policies}")
    lines.append(
        f"- **Fully enforced**: {fully_enforced_policies} ({100*fully_enforced_policies//max(total_policies,1)}%)"
    )
    lines.append(f"- **Partially enforced**: {partially_enforced_policies}")
    lines.append(
        f"- **Not enforced**: {total_policies - fully_enforced_policies - partially_enforced_policies}"
    )
    lines.append("")

    # Sort policies by enforcement rate (ascending - show gaps first)
    policy_stats = []
    for policy, rules in by_policy.items():
        total = len(rules)
        enforced = sum(1 for r in rules if r.get("coverage_status") == "enforced")
        rate = enforced / total if total > 0 else 0
        policy_stats.append((policy, rules, total, enforced, rate))

    policy_stats.sort(key=lambda x: (x[4], x[0]))  # Sort by rate (ascending), then name

    lines.append("## Policies by Enforcement Rate (Gaps First)")
    lines.append("")

    for policy, rules, total, enforced, rate in policy_stats:
        # Policy header
        policy_short = "/".join(policy.split("/")[-3:])  # Show last 3 path segments
        status_icon = "✅" if enforced == total else "⚠️" if enforced > 0 else "❌"

        lines.append(f"### {status_icon} {policy_short}")
        lines.append(f"**Full path**: `{policy}`  ")
        lines.append(f"**Enforcement**: {enforced}/{total} rules ({int(100*rate)}%)")
        lines.append("")

        # Sort rules: non-enforced first (gaps), then by rule_id
        rules_sorted = sorted(
            rules,
            key=lambda r: (
                r.get("coverage_status") == "enforced",  # False (gaps) come first
                r.get("rule", {}).get("rule_id", ""),
            ),
        )

        # Rules list
        for rule_entry in rules_sorted:
            rule = rule_entry.get("rule", {})
            rule_id = rule.get("rule_id", "unknown")
            statement = rule.get("statement", "")[:100]  # Truncate long statements
            if len(rule.get("statement", "")) > 100:
                statement += "..."
            status = rule_entry.get("coverage_status", "unknown")
            severity = rule.get("severity", "")

            if status == "enforced":
                icon = "✅"
                status_text = "ENFORCED"
            elif status == "partially_enforced":
                icon = "⚠️"
                status_text = "PARTIAL"
            else:
                icon = "❌"
                status_text = "DECLARED"
                if severity:
                    status_text += f" ({severity})"

            lines.append(f"- {icon} **`{rule_id}`**: {statement} _{status_text}_")

        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- ✅ **ENFORCED**: Active constitutional check with audit evidence")
    lines.append(
        "- ⚠️ **PARTIAL**: Declared in constitution but verification incomplete"
    )
    lines.append("- ❌ **DECLARED**: Written in constitution but no active enforcement")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- **Fully enforced policies** are battle-tested and reliable")
    lines.append("- **Partially enforced policies** have gaps - some rules lack checks")
    lines.append(
        "- **Not enforced policies** are aspirational - need checker implementation"
    )
    lines.append("")
    lines.append(
        "Policies are sorted with **gaps shown first** to prioritize implementation work."
    )
    lines.append("")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    output = generate_hierarchical_summary(repo_root)
    print("[OK] Hierarchical coverage summary generated")
    print(f"     Output: {output}")
    print(f"     View: cat {output}")
