# src/system/admin/guard.py
"""
Intent: Governance/validation guard commands exposed to the operator.

This module wires operator-friendly CLI commands on top of the pure logic in
`system.admin.guard_logic`. It *only* deals with inputs/outputs (CLI args,
printing, and writing evidence files) and intentionally keeps business logic
elsewhere so behavior stays testable and stable.

Commands
--------
- guard drift
    Compare capabilities declared in domain manifests with capabilities
    discovered in source code. Produces a JSON evidence file and optionally a
    human-readable summary.

    Examples:
      core-admin guard drift --format pretty
      core-admin guard drift --format json --output reports/drift.json
      core-admin guard drift --fail-on any --strict-intent
      core-admin guard drift --dry-run --format json

- guard kg-export
    Emit a minimal knowledge-graph artifact of discovered capabilities for
    downstream tooling.

Note: Defaults (format, fail policy, evidence path, labels) are read from
`.intent/meta.yaml` under:
  operator_experience.guard.drift
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml

from system.admin.guard_logic import run_drift
from system.admin.utils import should_fail
from system.guard.capability_discovery import collect_code_capabilities


def _load_ux_defaults(root: Path) -> Dict[str, Any]:
    """Extract UX-related defaults for the drift command from `.intent/meta.yaml`.

    Falls back to sensible built-in defaults if the file or keys are missing.
    This influences *only* presentation/paths, not detection behavior.
    """
    meta_path = root / ".intent" / "meta.yaml"
    if not meta_path.exists():
        return {
            "default_format": "pretty",
            "default_fail_on": "any",
            "evidence_path": "reports/drift_report.json",
            "labels": {
                "none": "NONE",
                "success": "✅ No capability drift",
                "failure": "🚨 Drift detected",
            },
        }
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    ux = raw.get("operator_experience", {}).get("guard", {}).get("drift", {})
    return {
        "default_format": ux.get("default_format", "pretty"),
        "default_fail_on": ux.get("default_fail_on", "any"),
        "evidence_path": ux.get("evidence_path", "reports/drift_report.json"),
        "labels": ux.get(
            "labels",
            {
                "none": "NONE",
                "success": "✅ No capability drift",
                "failure": "🚨 Drift detected",
            },
        ),
    }


def _is_clean(report: dict) -> bool:
    """Return True if the drift report contains no missing/undeclared/mismatched items."""
    return not (
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )


def _normalize_report(report: dict) -> dict:
    """Return a copy of the report with deterministic ordering for stable diffs."""
    norm = {
        "missing_in_code": sorted(set(report.get("missing_in_code", []))),
        "undeclared_in_manifest": sorted(set(report.get("undeclared_in_manifest", []))),
        "mismatched_mappings": sorted(
            report.get("mismatched_mappings", []),
            key=lambda m: (
                m.get("capability") or "",
                str(m.get("manifest")),
                str(m.get("code")),
            ),
        ),
    }
    # Preserve any extra keys deterministically
    for k in sorted(set(report.keys()) - set(norm.keys())):
        v = report[k]
        norm[k] = v
    return norm


def _print_pretty(report_dict: dict, labels: Dict[str, str]) -> None:
    """Print a compact, human-friendly summary using basic TTY styling."""
    status = labels["success"] if _is_clean(report_dict) else labels["failure"]
    typer.secho(f"\n--- {status} ---", bold=True)

    def print_section(title: str, items: List[str]):
        typer.secho(f"\n{title}:", bold=True)
        if not items:
            typer.secho(f"  {labels['none']}", fg=typer.colors.GREEN)
        else:
            for item in items:
                typer.secho(f"  - {item}", fg=typer.colors.YELLOW)

    print_section("Missing in code", report_dict.get("missing_in_code", []))
    print_section(
        "Undeclared in manifest", report_dict.get("undeclared_in_manifest", [])
    )

    mismatches = report_dict.get("mismatched_mappings", [])
    typer.secho("\nMismatched mappings:", bold=True)
    if not mismatches:
        typer.secho(f"  {labels['none']}", fg=typer.colors.GREEN)
    else:
        for m in mismatches:
            cap = m.get("capability")
            typer.secho(f"  - {cap}:", fg=typer.colors.YELLOW)
            typer.secho(f"    Manifest: {m.get('manifest')}", fg=typer.colors.YELLOW)
            typer.secho(f"    Code:     {m.get('code')}", fg=typer.colors.YELLOW)
    typer.echo("")


def register(app: typer.Typer) -> None:
    """Register the 'guard' command group with the main Admin CLI."""
    guard = typer.Typer(
        help=(
            "Governance & validation guards.\n\n"
            "Use 'guard drift' to detect capability drift between domain manifests "
            "and source code. Use 'guard kg-export' to emit a minimal capability graph."
        ),
        no_args_is_help=True,
    )
    app.add_typer(guard, name="guard")

    @guard.command("drift")
    def drift(
        root: Path = typer.Option(
            Path("."),
            help="Path to the repository root (where .intent/ lives).",
        ),
        output: Optional[Path] = typer.Option(
            None,
            help=(
                "Write the JSON evidence report here. "
                "Default is read from .intent/meta.yaml "
                "(operator_experience.guard.drift.evidence_path)."
            ),
        ),
        format: Optional[str] = typer.Option(
            None,
            help=(
                "Output mode: 'json' for machine-readable or 'pretty' for human-readable. "
                "Defaults to operator_experience.guard.drift.default_format."
            ),
        ),
        fail_on: Optional[str] = typer.Option(
            None,
            help=(
                "Exit with code 2 when drift of this type is present. "
                "Accepted values: 'any', 'missing', 'undeclared'. "
                "Defaults to operator_experience.guard.drift.default_fail_on."
            ),
        ),
        strict_intent: bool = typer.Option(
            False,
            "--strict-intent",
            help=(
                "Discovery mode that relies only on the constitutionally approved "
                "KnowledgeGraphBuilder (safer, potentially slower). Recommended for CI."
            ),
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Do not write the evidence file; print the report only.",
        ),
    ):
        """Compare manifest declarations vs. code to detect capability drift.

        Writes a JSON evidence file (unless --dry-run) and prints either a pretty
        summary or raw JSON. Exit codes: 0 = OK, 2 = drift detected per --fail-on policy.
        """
        ux = _load_ux_defaults(root)
        fmt = (format or ux["default_format"]).lower()
        fail_policy = (fail_on or ux["default_fail_on"]).lower()

        raw_report = run_drift(root, strict_intent)
        report = _normalize_report(raw_report)

        if not dry_run:
            final_output_path = output or (root / ux["evidence_path"])
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            final_output_path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        if fmt == "pretty":
            _print_pretty(report, ux["labels"])
        else:
            typer.echo(json.dumps(report, indent=2, sort_keys=True))

        if should_fail(report, fail_policy):
            raise typer.Exit(code=2)

    @guard.command("kg-export")
    def kg_export(
        root: Path = typer.Option(
            Path("."),
            help="Path to the repository root (where .intent/ lives).",
        ),
        output: Optional[Path] = typer.Option(
            None,
            help=(
                "Target file for the knowledge-graph artifact. "
                "Defaults to 'reports/knowledge_graph.json' under --root."
            ),
        ),
        include: Optional[List[str]] = typer.Option(
            None,
            help="Optional glob(s) to include (e.g., 'src/**.py'). If omitted, scan *.py.",
        ),
        exclude: Optional[List[str]] = typer.Option(
            None,
            help="Optional glob(s) to exclude from scanning.",
        ),
        prefer: str = typer.Option(
            "auto",
            case_sensitive=False,
            help=(
                "Source of truth for capability discovery: "
                "'auto' (prefer KGB when available), 'kgb' (require KGB), or 'grep' (fallback scan)."
            ),
        ),
    ):
        """Emit a minimal capability knowledge-graph artifact for downstream tools."""
        require_kgb = prefer.lower() == "kgb"
        caps = collect_code_capabilities(
            root,
            include_globs=include,
            exclude_globs=exclude,
            require_kgb=require_kgb,
        )
        nodes = [
            {"capability": k, "domain": v.domain, "owner": v.owner}
            for k, v in sorted(caps.items())
        ]
        out_path = output or (root / "reports" / "knowledge_graph.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"nodes": nodes}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        typer.echo(
            f"✅ Wrote knowledge-graph artifact with {len(nodes)} capability nodes -> {out_path}"
        )
