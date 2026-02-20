# src/mind/governance/audit_report_writer.py
"""
Report generation logic for audit post-processing results.

CONSTITUTIONAL ALIGNMENT (V2.6.0):
- Pure Logic: This module only formats data. It has no side effects.
- Resolves architecture.mind.no_filesystem_writes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


# ID: 6fba0c39-ebae-4a74-b2dd-f77b5fa6b4c6
def build_auto_ignored_markdown(
    timestamp: str, auto_ignored: Sequence[Mapping[str, object]]
) -> str:
    """Pure data transformation: formats data as Markdown. Returns a string."""
    grouped: dict[str, dict[str, list[str]]] = {}

    for item in auto_ignored:
        ep = str(item.get("entry_point_type") or "unknown")
        pat = str(item.get("pattern_name") or "—")
        grouped.setdefault(ep, {}).setdefault(pat, []).append(
            str(item.get("symbol_key") or "")
        )

    lines: list[str] = [
        "# Audit Auto-Ignored Symbols",
        "",
        f"- Generated: `{timestamp}`",
        f"- Total auto-ignored: **{len(auto_ignored)}**",
        "",
    ]

    for ep_type in sorted(grouped.keys()):
        lines.append(f"## {ep_type}")
        for pattern_name in sorted(grouped[ep_type].keys()):
            syms = grouped[ep_type][pattern_name]
            lines.append(f"### Pattern: {pattern_name}  _(n={len(syms)})_")
            for sym in sorted(syms):
                lines.append(f"- `{sym}`")
            lines.append("")

    return "\n".join(lines) + "\n"
