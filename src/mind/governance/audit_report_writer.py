# src/mind/governance/audit_report_writer.py

"""
Report generation for audit post-processing results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler


# ID: d3c25742-92e0-4e44-a00e-4eac082bb62a
def now_iso() -> str:
    """Generate ISO-formatted UTC timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ID: 8e7e9c72-916f-451f-adfa-248186c400ce
def relpath_under_repo(repo_root: Path, path: Path) -> str:
    """
    Convert path to repo-relative string.

    Raises:
        ValueError if path is outside repository boundary
    """
    abs_path = path if path.is_absolute() else (repo_root / path).resolve()
    repo_root = repo_root.resolve()

    if not abs_path.is_relative_to(repo_root):
        raise ValueError(f"Path must be under repo root: {path}")

    return str(abs_path.relative_to(repo_root))


# ID: b915ef98-e8e0-4a83-8c54-09efbedd5e02
def write_auto_ignored_reports(
    repo_root: Path,
    file_handler: FileHandler,
    reports_dir: str | Path,
    auto_ignored: Sequence[Mapping[str, object]],
) -> None:
    """
    Write JSON and Markdown reports of auto-ignored symbols.

    Args:
        repo_root: Repository root path
        file_handler: FileHandler for constitutional compliance
        reports_dir: Directory for report output
        auto_ignored: List of auto-ignored symbol metadata
    """
    timestamp = now_iso()
    reports_dir_path = Path(reports_dir)
    reports_rel_dir = relpath_under_repo(repo_root, reports_dir_path).rstrip("/")

    # Ensure directory exists via FileHandler
    file_handler.ensure_dir(reports_rel_dir)

    # Write JSON report
    json_rel_path = f"{reports_rel_dir}/audit_auto_ignored.json"
    payload = {
        "generated_at": timestamp,
        "total_auto_ignored": len(auto_ignored),
        "items": list(auto_ignored),
    }
    file_handler.write_runtime_json(json_rel_path, payload)

    # Write Markdown report
    md_rel_path = f"{reports_rel_dir}/audit_auto_ignored.md"
    markdown_content = _build_markdown_report(timestamp, auto_ignored)
    file_handler.write_runtime_text(md_rel_path, markdown_content)


def _build_markdown_report(
    timestamp: str, auto_ignored: Sequence[Mapping[str, object]]
) -> str:
    """Build markdown report grouped by entry_point_type and pattern_name."""
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
