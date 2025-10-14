# src/features/governance/audit_postprocessor.py
"""
Post-processing utilities for Constitutional Auditor findings.

This module provides:
  1) Severity downgrade for "dead-public-symbol" findings when the symbol
     has an allowed `entry_point_type` (as declared in
     .intent/mind/knowledge/entry_point_patterns.yaml).
  2) Auto-generated reports of all symbols auto-ignored-by-pattern to keep
     human visibility without polluting audit_ignore_policy.yaml.

Usage (programmatic):
    from src.features.governance.audit_postprocessor import (
        EntryPointAllowList,
        apply_entry_point_downgrade_and_report,
    )

    processed_findings = apply_entry_point_downgrade_and_report(
        findings=raw_findings,
        symbol_index=symbol_index,  # dict[str, dict] with entry_point_type, etc.
        reports_dir="reports",
        allow_list=EntryPointAllowList.default(),
        dead_rule_ids={"dead_public_symbol", "dead-public-symbol"},
        downgrade_to="info",  # or "warn"
        write_reports=True,
    )

Usage (CLI; optional):
    python -m src.features.governance.audit_postprocessor \
        --in findings.json --symbols symbols.json --out findings.processed.json --reports reports

Expectations:
  - `findings` is a list[dict] with keys like:
        rule_id: str
        severity: str  ("error"|"warn"|"info")
        symbol_key: str  (e.g., "src/foo.py::Foo.bar")
        message: str
        [any other fields are preserved]

  - `symbol_index` is a dict[str, dict] mapping symbol_key -> metadata dict, e.g.:
        {
          "entry_point_type": "cli_wrapper" | "data_model" | ...,
          "entry_point_justification": "matched pattern X",
          "pattern_name": "cli_wrapper_function",
          ...
        }

  - Caller persists the returned list if using programmatic API.

Notes:
  - This is intentionally narrow-scoped and duck-typed to avoid coupling
    to specific internal Finding/Symbol classes.
"""

from __future__ import annotations

import argparse

# src/features/governance/audit_postprocessor.py
import json
import sys
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from datetime import UTC, datetime
from pathlib import Path


# ID: 34bd4ecc-62ce-4d54-b72b-bfd2b14324ed
class EntryPointAllowList:
    """
    Allow-list of entry_point_type values for which we downgrade "dead-public-symbol"
    findings. This mirrors the generalized patterns you codified in
    `.intent/mind/knowledge/entry_point_patterns.yaml`.

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
) -> list[MutableMapping[str, object]]:
    """
    Process a list of findings and:
      - Downgrade severity for dead-public-symbol findings whose symbol entry_point_type
        is allowed by policy.
      - Generate a report listing all auto-ignored symbols (grouped by pattern/type).

    Returns a new list of findings (mutating the original items in place).
    """
    allow = allow_list or EntryPointAllowList.default()
    dead_ids = {r.strip() for r in dead_rule_ids if r and r.strip()}
    processed: list[MutableMapping[str, object]] = []
    auto_ignored: list[dict[str, object]] = []

    for f in findings:
        # Duck-typed access:
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
                # Track for auto-ignored report
                auto_ignored.append(
                    {
                        "symbol_key": symbol_key,
                        "entry_point_type": ep_type,
                        "pattern_name": pattern_name or None,
                        "justification": justification or None,
                        "original_rule_id": rule_id,
                        "downgraded_to": f["severity"],
                    }
                )

        processed.append(f)

    if write_reports:
        _write_reports(reports_dir, auto_ignored)

    return processed


def _write_reports(
    reports_dir: str | Path, auto_ignored: Sequence[Mapping[str, object]]
) -> None:
    """
    Emit both JSON and Markdown summaries of auto-ignored-by-pattern symbols.
    These are ephemeral audit artifacts (not part of the Constitution).
    """
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    ts = _now_iso()
    json_path = reports_path / "audit_auto_ignored.json"
    md_path = reports_path / "audit_auto_ignored.md"

    payload = {
        "generated_at": ts,
        "total_auto_ignored": len(auto_ignored),
        "items": list(auto_ignored),
    }
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Markdown summary grouped by entry_point_type then pattern_name
    grouped: dict[str, dict[str, list[str]]] = {}
    for item in auto_ignored:
        ep = str(item.get("entry_point_type") or "unknown")
        pat = str(item.get("pattern_name") or "—")
        grouped.setdefault(ep, {}).setdefault(pat, []).append(
            str(item.get("symbol_key") or "")
        )

    lines = [
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
            lines.append("")  # blank line

    md_path.write_text("\n".join(lines), encoding="utf-8")


# -----------------------------
# Optional CLI entrypoint
# -----------------------------
def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ID: a373b218-70a0-40fb-89e3-6815b9f76d2b
def main(argv: list[str] | None = None) -> int:
    """
    Minimal CLI to post-process existing auditor outputs.

    Example:
      python -m src.features.governance.audit_postprocessor \
        --in reports/audit_findings.json \
        --symbols reports/symbol_index.json \
        --out reports/audit_findings.processed.json \
        --reports reports \
        --downgrade-to info
    """
    parser = argparse.ArgumentParser(description="Audit findings post-processor")
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

    in_path = Path(args.in_path)
    symbols_path = Path(args.symbols_path)
    out_path = Path(args.out_path)
    reports_dir = Path(args.reports_dir)

    findings_obj = _load_json(in_path)
    symbols_obj = _load_json(symbols_path)

    if not isinstance(findings_obj, list):
        print("ERROR: findings JSON must be a list of objects.", file=sys.stderr)
        return 2
    if not isinstance(symbols_obj, dict):
        print(
            "ERROR: symbols JSON must be an object mapping symbol_key to metadata.",
            file=sys.stderr,
        )
        return 2

    processed = apply_entry_point_downgrade_and_report(
        findings=findings_obj,  # type: ignore[arg-type]
        symbol_index=symbols_obj,  # type: ignore[arg-type]
        reports_dir=reports_dir,
        allow_list=EntryPointAllowList.default(),
        dead_rule_ids=args.dead_rule_ids
        or ("dead_public_symbol", "dead-public-symbol"),
        downgrade_to=args.downgrade_to,
        write_reports=True,
    )

    _save_json(out_path, processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
