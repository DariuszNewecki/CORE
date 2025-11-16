# src/body/cli/logic/audit.py
"""
Implements high-level CI and system health checks, including the main constitutional audit.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shared.context import CoreContext
from shared.models import AuditFinding, AuditSeverity
from shared.utils.subprocess_utils import run_poetry_command

from src.mind.governance.auditor import ConstitutionalAuditor

console = Console()

# Global variable to store context, set by the main admin_cli.py
_context: CoreContext | None = None


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
    """Groups findings by check ID and prints a summary table."""
    grouped_findings: dict[tuple[str, str, AuditSeverity], list[str]] = defaultdict(
        list
    )
    for f in findings:
        location = str(f.file_path or "")
        if f.line_number:
            location += f":{f.line_number}"
        key = (f.check_id, f.message, f.severity)
        grouped_findings[key].append(location)

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
        key=lambda item: (item[0][2], item[0][0]),
        reverse=True,
    )

    for (check_id, message, severity), locations in sorted_items:
        table.add_row(
            severity_styles.get(severity, str(severity)),
            check_id,
            message,
            str(len(locations)),
        )

    console.print(table)
    console.print("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


async def _async_audit(severity: str, verbose: bool):
    """The core async logic for running the audit."""
    if _context is None:
        console.print("[bold red]Error: Context not initialized for audit[/bold red]")
        raise typer.Exit(code=1)

    auditor = ConstitutionalAuditor(_context.auditor_context)
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
            f"[bold red]Invalid severity level '{severity}'. Must be 'info', 'warning', or 'error'.[/bold red]"
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


# ID: a232d01a-26a1-417c-8911-225d6cf64288
def lint():
    """Checks code formatting and quality using Black and Ruff."""
    run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


# ID: dab15c7d-53b5-4340-9502-80ceca6abad7
def test_system():
    """Run the pytest suite."""
    run_poetry_command("🧪 Running tests with pytest...", ["pytest"])


# ID: ae47757e-0e9a-4527-93e3-57f6102e65a7
def audit(
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
):
    """Run a full constitutional self-audit and print a summary of findings."""
    # THE FIX: Pass the arguments to the async function.
    asyncio.run(_async_audit(severity=severity, verbose=verbose))
