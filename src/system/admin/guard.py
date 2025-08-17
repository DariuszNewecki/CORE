# src/system/admin/guard.py
"""
Intent: Governance/validation guard commands exposed to the operator.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from shared.logger import getLogger

from system.admin.utils import should_fail
from system.guard.capability_discovery import (
    collect_code_capabilities,
    load_manifest_capabilities,
)
from system.guard.drift_detector import detect_capability_drift, write_report

log = getLogger("core_admin")


# --- THIS IS THE FIX (Part 1 of 2) ---
# This helper no longer looks for a manifest file. It looks in meta.yaml.
def _load_ux_defaults(root: Path) -> Dict[str, Any]:
    """Extracts and returns UX-related default values from meta.yaml."""
    meta_path = root / ".intent" / "meta.yaml"
    if not meta_path.exists():
        # Provide sensible defaults if meta.yaml is missing
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
    """Determines if a report is clean."""
    return not (
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )


def _print_table(report_dict: dict, labels: Dict[str, str]) -> None:
    """Prints a formatted table of the drift report."""
    table = Table(show_header=True, header_style="bold", title="Capability Drift")
    table.add_column("Section", style="bold")
    table.add_column("Values")

    def row(title: str, items: List[str]):
        """Adds a row to a table with a title and formatted list of items, showing '[none]' if items is empty."""
        if not items:
            table.add_row(title, f"[bold green]{labels['none']}[/bold green]")
        else:
            formatted_items = "\n".join(f"- {it}" for it in items)
            table.add_row(title, f"[yellow]{formatted_items}[/yellow]")

    row("Missing in code", report_dict.get("missing_in_code", []))
    row("Undeclared in manifest", report_dict.get("undeclared_in_manifest", []))

    mismatches = report_dict.get("mismatched_mappings", [])
    if not mismatches:
        table.add_row(
            "Mismatched mappings", f"[bold green]{labels['none']}[/bold green]"
        )
    else:
        lines = [
            f"- {m.get('capability')}: manifest(...) != code(...)" for m in mismatches
        ]
        table.add_row(
            "Mismatched mappings", "[yellow]" + "\n".join(lines) + "[/yellow]"
        )

    status = (
        f"[bold green]{labels['success']}[/bold green]"
        if _is_clean(report_dict)
        else f"[bold red]{labels['failure']}[/bold red]"
    )
    rprint(Panel.fit(table, title=status))


def _print_pretty(report_dict: dict, labels: Dict[str, str]) -> None:
    """Prints a user-friendly summary of the drift report."""
    _print_table(report_dict, labels)


def register(app: typer.Typer) -> None:
    """Registers the 'guard' command group with the CLI."""
    guard = typer.Typer(help="Governance/validation guards")
    app.add_typer(guard, name="guard")

    @guard.command("drift")
    def drift(
        root: Path = typer.Option(Path("."), help="Repository root."),
        output: Optional[Path] = typer.Option(
            None, help="Path for JSON evidence report."
        ),
        format: Optional[str] = typer.Option(None, help="json|table|pretty"),
        fail_on: Optional[str] = typer.Option(None, help="any|missing|undeclared"),
        strict_intent: Optional[bool] = typer.Option(None, help="Require KGB."),
        include: Optional[List[str]] = typer.Option(None, help="Include globs."),
        exclude: Optional[List[str]] = typer.Option(None, help="Exclude globs."),
    ):
        """Compares manifest vs code to detect capability drift."""
        ux = _load_ux_defaults(root)
        fmt = (format or ux["default_format"]).lower()
        fail_policy = (fail_on or ux["default_fail_on"]).lower()

        manifest_caps = load_manifest_capabilities(root)
        code_caps = collect_code_capabilities(
            root, include, exclude, require_kgb=strict_intent
        )

        report = detect_capability_drift(manifest_caps, code_caps)
        report_dict = report.to_dict()

        write_report(output or (root / ux["evidence_path"]), report)

        if fmt in ("table", "pretty"):
            _print_pretty(report_dict, ux["labels"])
        else:
            typer.echo(json.dumps(report_dict, indent=2))

        if should_fail(report_dict, fail_policy):
            raise typer.Exit(code=2)

    @guard.command("kg-export")
    def kg_export(
        root: Path = typer.Option(Path("."), help="Repository root."),
        output: Optional[Path] = typer.Option(None, help="Artifact file."),
        include: Optional[List[str]] = typer.Option(None, help="Include globs."),
        exclude: Optional[List[str]] = typer.Option(None, help="Exclude globs."),
        prefer: str = typer.Option("auto", case_sensitive=False, help="auto|kgb|grep"),
    ):
        """Emits a minimal knowledge-graph artifact with capability nodes."""
        require_kgb = prefer.lower() == "kgb"
        caps = collect_code_capabilities(
            root, include_glogaits=include, exclude_globs=exclude, require_kgb=require_kgb
        )
        nodes = [
            {"capability": k, "domain": v.domain, "owner": v.owner}
            for k, v in sorted(caps.items())
        ]

        out_path = output or (root / "reports" / "knowledge_graph.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"nodes": nodes}, indent=2), encoding="utf-8")
        rprint(
            f"[bold green]✅[/bold green] Wrote knowledge-graph artifact with [bold]{len(nodes)}[/bold] capability nodes -> {out_path}"
        )
