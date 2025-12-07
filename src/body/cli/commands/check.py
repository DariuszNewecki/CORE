# src/body/cli/commands/check.py
"""
Registers and implements the verb-based 'check' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
Handles UI presentation for audit results.
"""

from __future__ import annotations

from collections import defaultdict

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shared.action_types import ActionResult
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from body.cli.logic.audit import lint, run_audit_workflow, test_system
from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.logic.diagnostics import policy_coverage

logger = getLogger(__name__)
console = Console()

check_app = typer.Typer(
    help="Read-only validation and health checks.", no_args_is_help=True
)


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
    grouped_findings = defaultdict(list)

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


@check_app.command("audit")
@core_command(dangerous=False)
# ID: ca09d5e2-b0af-4ed2-9c8b-9dcb515e3c00
async def audit_cmd(
    ctx: typer.Context,
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
) -> None:
    """
    Run the full constitutional self-audit.

    Checks:
    - Knowledge Graph Integrity
    - Policy Compliance
    - Safety & Security Rules
    - Architecture & Dependency Injection
    """
    core_context: CoreContext = ctx.obj

    # Logic layer runs the audit (HEADLESS)
    passed, all_findings = await run_audit_workflow(core_context)

    # Command layer handles presentation (UI)
    try:
        min_severity = AuditSeverity[severity.upper()]
    except KeyError:
        console.print(
            f"[bold red]Invalid severity level '{severity}'. "
            "Must be 'info', 'warning', or 'error'.[/bold red]"
        )
        raise typer.Exit(code=1)

    # Filter for display
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    unassigned_count = len(
        [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
    )

    # Build Summary Table
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


@check_app.command("lint")
@core_command(dangerous=False)
# ID: 8428c471-1a01-4327-9640-52987ef7130d
def lint_cmd(ctx: typer.Context) -> None:
    """
    Check code formatting and quality using Black and Ruff.
    """
    # This is a synchronous wrapper around subprocess calls
    lint()


@check_app.command("tests")
@core_command(dangerous=False)
# ID: 1e60b497-4db8-4d00-96f2-945ac2d096da
def tests_cmd(ctx: typer.Context) -> None:
    """
    Run the project test suite via pytest.
    """
    test_system()


@check_app.command("diagnostics")
@core_command(dangerous=False)
# ID: 9f9ebe73-c1b6-478f-aa52-21adcb64f1e0
def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    policy_coverage()


@check_app.command("system")
@core_command(dangerous=False)
# ID: 461df3d1-5724-44be-a11e-691b9d88d5e0
async def system_cmd(ctx: typer.Context) -> None:
    """
    Run all system health checks: Lint, Tests, and Constitutional Audit.
    """
    console.rule("[bold cyan]1. Code Quality (Lint)[/bold cyan]")
    lint()

    console.rule("[bold cyan]2. System Integrity (Tests)[/bold cyan]")
    test_system()

    console.rule("[bold cyan]3. Constitutional Compliance (Audit)[/bold cyan]")
    # Reuse the audit command logic
    await audit_cmd(ctx)


@check_app.command("body-ui")
@core_command(dangerous=False)
# ID: 3a985f2b-4d76-4c28-9f1e-8e3d2a7b6c9d
async def check_body_ui_cmd(ctx: typer.Context) -> None:
    """
    Check for Body layer UI contract violations (print, rich usage, os.environ).

    Body modules must be HEADLESS.
    """
    console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")

    result: ActionResult = await check_body_contracts()

    if not result.ok:
        violations = result.data.get("violations", [])
        console.print(f"\n[red]❌ Found {len(violations)} contract violations:[/red]\n")

        # Group by file for cleaner output
        by_file = {}
        for v in violations:
            path = v.get("file", "unknown")
            by_file.setdefault(path, []).append(v)

        for path, file_violations in by_file.items():
            console.print(f"[bold]{path}[/bold]:")
            for v in file_violations:
                rule = v.get("rule_id", "unknown")
                msg = v.get("message", "")
                line = v.get("line")
                loc = f"line {line}" if line else "general"
                console.print(f"  - [{rule}] {msg} ({loc})")
            console.print()

        console.print(
            "[yellow]💡 Run 'core-admin fix body-ui --write' to auto-fix.[/yellow]"
        )
        raise typer.Exit(1)

    console.print("[green]✅ Body contracts compliant.[/green]")
