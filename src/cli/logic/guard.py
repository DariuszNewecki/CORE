"""
Intent: Governance/validation guard commands exposed to the operator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from shared.logger import getLogger

log = getLogger("core_admin")


def _find_manifest_path(root: Path, explicit: Optional[Path]) -> Optional[Path]:
    """Locate and return the path to the project manifest file, or None."""
    if explicit and explicit.exists():
        return explicit
    for p in (root / ".intent/project_manifest.yaml", root / ".intent/manifest.yaml"):
        if p.exists():
            return p
    return None


def _load_raw_manifest(root: Path, explicit: Optional[Path]) -> Dict[str, Any]:
    """Loads and parses a YAML manifest file, returning an empty dict if not found."""
    path = _find_manifest_path(root, explicit)
    if not path:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def _ux_defaults(root: Path, explicit: Optional[Path]) -> Dict[str, Any]:
    """Extracts and returns UX-related default values from the manifest."""
    raw = _load_raw_manifest(root, explicit)
    ux = raw.get("operator_experience", {}).get("guard", {}).get("drift", {})
    return {
        "default_format": ux.get("default_format", "json"),
        "default_fail_on": ux.get("default_fail_on", "any"),
        "strict_default": bool(ux.get("strict_default", False)),
        "evidence_json": bool(ux.get("evidence_json", True)),
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

    # ID: 2b132e4d-1d2b-48e3-92bb-cbaea04dfd0d
    def row(title: str, items: List[str]):
        """Adds a row with a formatted list of items."""
        if not items:
            table.add_row(title, f"[bold green]{labels['none']}[/bold green]")
        else:
            table.add_row(
                title, f'[yellow]{'\\n'.join((f'- {it}' for it in items))}[/yellow]'
            )

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
