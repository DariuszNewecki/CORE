# src/mind/governance/audit_postprocessor.py
"""
Post-processing utilities for Constitutional Auditor findings.

This module provides:
  1) Severity downgrade for "dead-public-symbol" findings when the symbol
     has an allowed `entry_point_type`.
  2) Auto-generated reports of all symbols auto-ignored-by-pattern to keep
     human visibility without polluting audit_ignore_policy.yaml.

Constitutional constraint (important):
  - This module MUST NOT perform direct filesystem mutations (mkdir/write_text).
  - All writes must go through FileHandler (approved mutation surface).

Therefore:
  - Programmatic usage supports an injected FileHandler.
  - CLI mode requires a repo root and uses FileHandler for all output writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 34bd4ecc-62ce-4d54-b72b-bfd2b14324ed
class EntryPointAllowList:
    """
    Allow-list of entry_point_type values for which we downgrade "dead-public-symbol"
    findings.

    You can extend/override via constructor or by using .default() and modifying the set.
    """

    def __init__(self, allowed_types: Iterable[str]) -> None:
        self.allowed = {t.strip() for t in allowed_types if t and t.strip()}

    @classmethod
    # ID: f789f14f-26bc-4cc4-b889-17c55c6c5f77
    def default(cls) -> EntryPointAllowList:
        return cls(
            allowed_types=[
                # Structural/data constructs
                "data_model",
                "enum",
                "magic_method",
                "visitor_method",
                "base_class",
                "boilerplate_method",
                # CLI & wrappers
                "cli_command",
                "cli_wrapper",
                "registry_accessor",
                # Orchestration/factories
                "orchestrator",
                "factory",
                # Providers/adapters/clients
                "provider_method",
                "client_surface",
                "client_adapter",
                "io_handler",
                "git_adapter",
                "utility_function",
                # Knowledge & governance pipelines
                "knowledge_core",
                "governance_check",
                "auditor_pipeline",
                # Capabilities
                "capability",
            ]
        )

    def __contains__(self, entry_point_type: str | None) -> bool:
        return bool(entry_point_type) and entry_point_type in self.allowed


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_symbol_meta(
    symbol_index: Mapping[str, Mapping[str, object]], symbol_key: str
) -> Mapping[str, object]:
    return symbol_index.get(symbol_key, {}) or {}


def _relpath_under_repo(repo_root: Path, path: Path) -> str:
    """
    Convert an absolute or relative path to a repo-relative string.

    Raises:
        ValueError if path is outside the repo boundary.
    """
    abs_path = path if path.is_absolute() else (repo_root / path).resolve()
    repo_root = repo_root.resolve()
    if not abs_path.is_relative_to(repo_root):
        raise ValueError(f"reports_dir must be under repo root: {path}")
    return str(abs_path.relative_to(repo_root))


def _write_reports_via_filehandler(
    *,
    repo_root: Path,
    file_handler: FileHandler,
    reports_dir: str | Path,
    auto_ignored: Sequence[Mapping[str, object]],
) -> None:
    """
    Emit both JSON and Markdown summaries of auto-ignored-by-pattern symbols.

    Writes go through FileHandler (the approved mutation surface).
    """
    ts = _now_iso()

    reports_dir_path = Path(reports_dir)
    reports_rel_dir = _relpath_under_repo(repo_root, reports_dir_path).rstrip("/")

    # Ensure directory exists (mkdir is a mutation => FileHandler)
    file_handler.ensure_dir(reports_rel_dir)

    json_rel_path = f"{reports_rel_dir}/audit_auto_ignored.json"
    md_rel_path = f"{reports_rel_dir}/audit_auto_ignored.md"

    payload = {
        "generated_at": ts,
        "total_auto_ignored": len(auto_ignored),
        "items": list(auto_ignored),
    }
    file_handler.write_runtime_json(json_rel_path, payload)

    # Markdown summary grouped by entry_point_type then pattern_name
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
        f"- Generated: `{ts}`",
        f"- Total auto-ignored: **{len(auto_ignored)}**",
        "",
    ]

    for ep_type in sorted(grouped.keys()):
        lines.append(f"## {ep_type}")
        for pattern_name in sorted(grouped[ep_type].keys()):
            syms = grouped[ep_type][pattern_name]
            lines.append(f"### Pattern: {pattern_name}  _(n={len(syms)})_")
            for s in sorted(syms):
                lines.append(f"- `{s}`")
            lines.append("")

    file_handler.write_runtime_text(md_rel_path, "\n".join(lines) + "\n")


# ID: b96e63c3-67b3-44b2-a19a-197368a8aba0
def apply_entry_point_downgrade_and_report(
    *,
    findings: Sequence[MutableMapping[str, object]],
    symbol_index: Mapping[str, Mapping[str, object]],
    reports_dir: str | Path = "reports",
    allow_list: EntryPointAllowList | None = None,
    dead_rule_ids: Iterable[str] = ("dead_public_symbol", "dead-public-symbol"),
    downgrade_to: str = "info",  # could be "warn" if you want a gentle nudge
    write_reports: bool = True,
    # NEW: enforced mutation surface
    file_handler: FileHandler | None = None,
    repo_root: Path | None = None,
) -> list[MutableMapping[str, object]]:
    """
    Process a list of findings and:
      - Downgrade severity for dead-public-symbol findings whose symbol entry_point_type
        is allowed by policy.
      - Optionally generate a report listing all auto-ignored symbols.

    Returns:
        A new list of findings (the original items may be mutated in place).

    Constitutional note:
        If write_reports=True, file_handler MUST be provided (to avoid direct writes).
    """
    allow = allow_list or EntryPointAllowList.default()
    dead_ids = {r.strip() for r in dead_rule_ids if r and r.strip()}
    processed: list[MutableMapping[str, object]] = []
    auto_ignored: list[dict[str, object]] = []

    for f in findings:
        rule_id = str(f.get("rule_id", "") or "")
        symbol_key = str(f.get("symbol_key", "") or "")
        severity = str(f.get("severity", "") or "").lower()

        if rule_id in dead_ids and symbol_key:
            meta = _safe_symbol_meta(symbol_index, symbol_key)
            ep_type = str(meta.get("entry_point_type", "") or "")
            pattern_name = str(meta.get("pattern_name", "") or "")
            justification = str(meta.get("entry_point_justification", "") or "")

            if ep_type in allow:
                # Downgrade severity (only if current is higher)
                if severity in {"error", "warn"}:
                    f["severity"] = downgrade_to
                auto_ignored.append(
                    {
                        "symbol_key": symbol_key,
                        "entry_point_type": ep_type,
                        "pattern_name": pattern_name or None,
                        "justification": justification or None,
                        "original_rule_id": rule_id,
                        "downgraded_to": f.get("severity"),
                    }
                )

        processed.append(f)

    if write_reports:
        if file_handler is None:
            raise ValueError(
                "write_reports=True requires file_handler (no direct FS writes allowed)."
            )
        rr = repo_root or getattr(file_handler, "repo_path", None)
        if not isinstance(rr, Path):
            raise ValueError(
                "repo_root could not be determined; pass repo_root explicitly."
            )

        _write_reports_via_filehandler(
            repo_root=rr,
            file_handler=file_handler,
            reports_dir=reports_dir,
            auto_ignored=auto_ignored,
        )

    return processed


# -----------------------------
# Optional CLI entrypoint
# -----------------------------
def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


# ID: a373b218-70a0-40fb-89e3-6815b9f76d2b
def main(argv: list[str] | None = None) -> int:
    """
    Minimal CLI to post-process existing auditor outputs.

    Example:
      python -m mind.governance.audit_postprocessor \
        --repo-root /opt/dev/CORE \
        --in reports/audit_findings.json \
        --symbols reports/symbol_index.json \
        --out reports/audit_findings.processed.json \
        --reports reports \
        --downgrade-to info
    """
    parser = argparse.ArgumentParser(description="Audit findings post-processor")
    parser.add_argument(
        "--repo-root",
        dest="repo_root",
        required=True,
        help="Repository root (used for guarded writes via FileHandler).",
    )
    parser.add_argument(
        "--in", dest="in_path", required=True, help="Input findings JSON path"
    )
    parser.add_argument(
        "--symbols", dest="symbols_path", required=True, help="Symbol index JSON path"
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Output (processed findings) JSON path",
    )
    parser.add_argument(
        "--reports", dest="reports_dir", default="reports", help="Reports directory"
    )
    parser.add_argument(
        "--downgrade-to",
        dest="downgrade_to",
        default="info",
        choices=["info", "warn"],
        help="Target severity for allowed entry points",
    )
    parser.add_argument(
        "--dead-rule-id",
        dest="dead_rule_ids",
        action="append",
        default=None,
        help="Add/override dead-public-symbol rule id(s). Can be passed multiple times.",
    )

    args = parser.parse_args(argv or sys.argv[1:])

    repo_root = Path(args.repo_root).resolve()
    fh = FileHandler(str(repo_root))

    in_path = (
        (repo_root / args.in_path).resolve()
        if not Path(args.in_path).is_absolute()
        else Path(args.in_path)
    )
    symbols_path = (
        (repo_root / args.symbols_path).resolve()
        if not Path(args.symbols_path).is_absolute()
        else Path(args.symbols_path)
    )
    out_path = (
        (repo_root / args.out_path).resolve()
        if not Path(args.out_path).is_absolute()
        else Path(args.out_path)
    )

    findings_obj = _load_json(in_path)
    symbols_obj = _load_json(symbols_path)

    if not isinstance(findings_obj, list):
        logger.error("findings JSON must be a list of objects.")
        return 2
    if not isinstance(symbols_obj, dict):
        logger.error("symbols JSON must be an object mapping symbol_key to metadata.")
        return 2

    processed = apply_entry_point_downgrade_and_report(
        findings=findings_obj,  # type: ignore[arg-type]
        symbol_index=symbols_obj,  # type: ignore[arg-type]
        reports_dir=args.reports_dir,
        allow_list=EntryPointAllowList.default(),
        dead_rule_ids=args.dead_rule_ids
        or ("dead_public_symbol", "dead-public-symbol"),
        downgrade_to=args.downgrade_to,
        write_reports=True,
        file_handler=fh,
        repo_root=repo_root,
    )

    # Write processed findings via FileHandler (guarded)
    out_rel = _relpath_under_repo(repo_root, out_path)
    fh.write_runtime_json(out_rel, processed)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
