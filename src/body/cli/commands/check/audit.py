# src/body/cli/commands/check/audit.py
# ID: d9e8be26-e5e2-4015-899b-8741adaa820c

"""
Core audit commands: audit.
Refactored to use the canonical CoreContext provided by the framework.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.cli.commands.check.converters import parse_min_severity
from body.cli.commands.check.formatters import (
    print_summary_findings,
    print_verbose_findings,
)
from mind.governance.auditor import ConstitutionalAuditor
from shared.cli_utils import core_command
from shared.models import AuditFinding, AuditSeverity


console = Console()


def _to_audit_finding(raw: dict) -> AuditFinding:
    severity_map = {
        "info": AuditSeverity.INFO,
        "warning": AuditSeverity.WARNING,
        "error": AuditSeverity.ERROR,
    }
    raw_severity = str(raw.get("severity", "info")).lower()
    severity = severity_map.get(raw_severity, AuditSeverity.INFO)
    return AuditFinding(
        check_id=raw.get("check_id", "unknown"),
        severity=severity,
        message=raw.get("message", ""),
        file_path=raw.get("file_path"),
        line_number=raw.get("line_number"),
        context=raw.get("context", {}),
    )


# ID: a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6
@core_command(dangerous=False)
# ID: 2a6833cf-af2f-432f-8423-dad36e20d936
async def audit_cmd(
    ctx: typer.Context,
    target: Path = typer.Argument(Path("src"), help="File or directory to audit."),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Minimum severity level.",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show individual findings."
    ),
) -> None:
    """
    Run the full constitutional self-audit.
    """
    min_severity = parse_min_severity(severity)

    # CONSTITUTIONAL FIX: Use the context already wired by the framework
    auditor_context = ctx.obj.auditor_context
    auditor = ConstitutionalAuditor(auditor_context)

    # EXECUTE THE UNIFIED AUDIT
    raw_findings = await auditor.run_full_audit_async()
    all_findings = [_to_audit_finding(f) for f in raw_findings]

    # PRESENTATION
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]
    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]
    infos = [f for f in all_findings if f.severity == AuditSeverity.INFO]

    passed = len(errors) == 0

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_row("Total Findings:", str(len(all_findings)))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    summary_table.add_row("Info:", f"[cyan]{len(infos)}[/cyan]")

    title = "✅ AUDIT PASSED" if passed else "❌ AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)
