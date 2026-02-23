# src/body/cli/logic/governance/renderer.py

"""Refactored logic for src/body/cli/logic/governance/renderer.py."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


# ID: a466a91e-d15a-475f-99fb-d7d8f20ffdf4
def render_summary(coverage_data: dict[str, Any]) -> str:
    entries, summary, metadata = (
        coverage_data.get("entries", []),
        coverage_data.get("summary", {}),
        coverage_data.get("metadata", {}),
    )
    enforced = sorted(
        [e for e in entries if e.get("coverage_status") == "enforced"],
        key=lambda x: x.get("rule", {}).get("rule_id", ""),
    )
    declared = [e for e in entries if e.get("coverage_status") == "declared_only"]

    lines = ["# Enforcement Coverage Summary", "", "## Totals", ""]
    lines.append(f"- Total rules: {summary.get('rules_total', 0)}")
    lines.append(f"- Enforced (executed): {summary.get('rules_enforced', 0)}")
    lines.append(
        f"- Implementable (not executed): {summary.get('rules_implementable', 0)}"
    )
    lines.append(
        f"- Declared only (not implementable): {summary.get('rules_declared_only', 0)}"
    )
    lines.append(f"- Execution rate: {summary.get('execution_rate', 0)}%")
    lines.append(
        f"\n**Evidence key used**: `{metadata.get('evidence_key_used', 'unknown')}`\n"
    )

    lines.append("## Enforced rules\n")
    if not enforced:
        lines.append("_None yet._")
    else:
        for e in enforced:
            lines.append(f"- `{e['rule']['rule_id']}` — {e['rule']['policy']}")

    lines.append("\n## Top gaps (highest severity first)\n")
    sev_rank = {"error": 0, "warn": 1, "warning": 1, "info": 2, "": 3}
    gaps = sorted(
        [
            (
                str(e["rule"].get("severity", "")).lower(),
                e["rule"]["rule_id"],
                e["rule"]["policy"],
            )
            for e in declared
        ],
        key=lambda x: (sev_rank.get(x[0], 9), x[1]),
    )

    for sev, rid, pol in gaps[:25]:
        lines.append(f"- **{sev or 'unknown'}** `{rid}` — {pol}")
    return "\n".join(lines) + "\n"


# ID: eec5766e-a5a2-4bc9-9d7e-cd9af1cc4b35
def render_hierarchical(coverage_data: dict[str, Any]) -> str:
    entries, metadata = (
        coverage_data.get("entries", []),
        coverage_data.get("metadata", {}),
    )
    by_policy = defaultdict(list)
    for entry in entries:
        by_policy[str(entry["rule"]["policy"])].append(entry)

    lines = [
        "# Enforcement Coverage by Policy",
        "",
        f"**Generated**: {metadata.get('generated_at_utc', 'unknown')}",
        "",
        "## Summary",
    ]
    lines.append(f"- **Total policies**: {len(by_policy)}\n")

    stats = []
    for pol, rules in by_policy.items():
        total = len(rules)
        exec_c = sum(1 for r in rules if r["coverage_status"] == "enforced")
        stats.append((pol, rules, total, exec_c, exec_c / total if total > 0 else 0))

    for pol, rules, total, exec_c, rate in sorted(stats, key=lambda x: (x[4], x[0])):
        icon = "✅" if total > 0 and exec_c == total else ("⚠️" if exec_c > 0 else "❌")
        lines.append(
            f"### {icon} {pol}\n**Executed**: {exec_c}/{total} rules ({int(100 * rate)}%)\n"
        )
        for re in sorted(rules, key=lambda r: r["rule"]["rule_id"]):
            status = re["coverage_status"]
            s_icon = (
                "✅"
                if status == "enforced"
                else ("🟦" if status == "implementable" else "❌")
            )
            lines.append(
                f"- {s_icon} **`{re['rule']['rule_id']}`**: {re['rule']['statement'][:100]}..."
            )
        lines.append("")

    lines.extend(
        [
            "---",
            "## Legend",
            "- ✅ **EXECUTED**: Rule was executed in latest audit evidence",
            "- 🟦 **IMPLEMENTABLE**: Engine exists but audit did not execute it",
            "- ❌ **DECLARED**: Rule exists but is not implementable",
        ]
    )
    return "\n".join(lines) + "\n"
