# src/body/cli/logic/audit.py
"""
Provides functionality for the audit module.

Refactored to be stateless and pure async (logic layer).
"""

from __future__ import annotations

from collections import defaultdict

import typer
from mind.governance.auditor import ConstitutionalAuditor
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shared.context import CoreContext
from shared.models import AuditFinding, AuditSeverity
from shared.utils.subprocess_utils import run_poetry_command

console = Console()


def _print_verbose_findings(findings: list[AuditFinding]):
    """Prints every single finding in a detailed table for verbose output."""
    table = Table(
        title="[bold]Verbose Audit Findings[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="cyan")
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("File:Line", style="yellow")

    severity_styles = {
        AuditSeverity.ERROR: "[bold red]ERROR[/bold red]",
        AuditSeverity.WARNING: "[bold yellow]WARNING[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }

    for finding in findings:
        location = str(finding.file_path or "")
        if finding.line_number:
            location += f":{finding.line_number}"

        table.add_row(
            severity_styles.get(finding.severity, str(finding.severity)),
            finding.check_id,
            finding.message,
            location,
        )
    console.print(table)


def _print_summary_findings(findings: list[AuditFinding]):
    """Groups findings by check ID only and prints a summary table."""
    grouped_findings: dict[tuple[str, AuditSeverity], list[AuditFinding]] = defaultdict(
        list
    )

    for f in findings:
        key = (f.check_id, f.severity)
        grouped_findings[key].append(f)

    table = Table(
        title="[bold]Audit Findings Summary[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="cyan")
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("Occurrences", style="yellow", justify="right")

    severity_styles = {
        AuditSeverity.ERROR: "[bold red]ERROR[/bold red]",
        AuditSeverity.WARNING: "[bold yellow]WARNING[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }

    # Sort by severity (highest first), then by check_id
    sorted_items = sorted(
        grouped_findings.items(),
        key=lambda item: (item[0][1], item[0][0]),
        reverse=True,
    )

    for (check_id, severity), finding_list in sorted_items:
        # Take the first message as representative for the check_id
        representative_message = finding_list[0].message

        table.add_row(
            severity_styles.get(severity, str(severity)),
            check_id,
            representative_message,
            str(len(finding_list)),
        )

    console.print(table)
    console.print("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


# ID: 7de7e5c2-0fbf-4028-8111-e3722b7d0ad9
async def run_audit_workflow(
    context: CoreContext, severity: str = "warning", verbose: bool = False
) -> None:
    """
    The core async logic for running the audit.

    Args:
        context: The application context containing the auditor_context.
        severity: Minimum severity level to report ("info", "warning", "error").
        verbose: Whether to print detailed findings.
    """
    auditor = ConstitutionalAuditor(context.auditor_context)
    all_findings_dicts = await auditor.run_full_audit_async()

    severity_map = {str(s): s for s in AuditSeverity}
    all_findings = []
    for f_dict in all_findings_dicts:
        severity_str = f_dict.get("severity", "info")
        f_dict["severity"] = severity_map.get(severity_str, AuditSeverity.INFO)
        all_findings.append(AuditFinding(**f_dict))

    unassigned_count = len(
        [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
    )
    blocking_errors = [f for f in all_findings if f.severity.is_blocking]
    passed = not bool(blocking_errors)

    try:
        min_severity = AuditSeverity[severity.upper()]
    except KeyError:
        console.print(
            f"[bold red]Invalid severity level '{severity}'. "
            "Must be 'info', 'warning', or 'error'.[/bold red]"
        )
        raise typer.Exit(code=1)

    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")

    title = "✅ AUDIT PASSED" if passed else "❌ AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            _print_verbose_findings(filtered_findings)
        else:
            _print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)


# ID: 09884f64-313e-4f9d-84d0-de9e2d16a8d3
def lint() -> None:
    """Checks code formatting and quality using Black and Ruff."""
    run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


# ID: 0a52d8ef-18a6-40c6-9ffe-95b9f9c295e4
def test_system() -> None:
    """Run the pytest suite."""
    run_poetry_command("🧪 Running tests with pytest...", ["pytest"])
