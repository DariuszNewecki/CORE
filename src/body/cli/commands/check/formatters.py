# src/body/cli/commands/check/formatters.py
"""
Output formatters for audit results.

Handles Rich UI presentation of findings, summaries, and statistics.
All formatting logic lives here - keeps command code clean.
"""

from __future__ import annotations

from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.models import AuditFinding, AuditSeverity


console = Console()


# ID: 8802195d-91be-49bb-8739-f40873a702eb
def print_verbose_findings(findings: list[AuditFinding]) -> None:
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


# ID: b2c3d4e5-f678-90ab-cdef-1234567890ab
def print_summary_findings(findings: list[AuditFinding]) -> None:
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
        representative_message = finding_list[0].message
        table.add_row(
            severity_styles.get(severity, str(severity)),
            check_id,
            representative_message,
            str(len(finding_list)),
        )

    console.print(table)
    console.print("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


# ID: c3d4e5f6-7890-abcd-ef12-34567890abcd
def print_audit_summary(
    *,
    passed: bool,
    errors: list[AuditFinding],
    warnings: list[AuditFinding],
    unassigned_count: int | None = None,
    title_prefix: str = "",
) -> None:
    """Print audit summary panel with pass/fail status."""
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")

    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")

    if unassigned_count is not None:
        summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")

    title = (
        f"✅ {title_prefix}AUDIT PASSED" if passed else f"❌ {title_prefix}AUDIT FAILED"
    )
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))


# ID: d4e5f6a7-8901-bcde-f123-4567890abcde
def print_filtered_audit_summary(
    *,
    passed: bool,
    stats: dict,
    errors: list[AuditFinding],
    warnings: list[AuditFinding],
) -> None:
    """Print summary for filtered/focused audit runs."""
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")

    summary_table.add_row("Total Rules:", str(stats["total_rules"]))
    summary_table.add_row("Filtered Rules:", str(stats["filtered_rules"]))
    summary_table.add_row("Executed Rules:", str(stats["executed_rules"]))
    summary_table.add_row("Failed Rules:", f"[red]{stats.get('failed_rules', 0)}[/red]")
    summary_table.add_row("", "")
    summary_table.add_row("Total Findings:", str(stats["total_findings"]))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")

    title = "✅ FILTERED AUDIT PASSED" if passed else "❌ FILTERED AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))


# ID: e5f6a7b8-9012-cdef-1234-567890abcdef
def print_executed_rules(executed_rules: set[str]) -> None:
    """Print list of executed rules."""
    if not executed_rules:
        return

    console.print("\n[dim]Executed rules:[/dim]")
    for rule_id in sorted(executed_rules):
        console.print(f"  [dim]• {rule_id}[/dim]")


# ID: f6a7b8c9-0123-def1-2345-67890abcdef1
def print_migration_delta(*, legacy_executed: set[str], v2_rule_ids: set[str]) -> None:
    """Print migration delta showing legacy vs v2 coverage."""
    legacy_only = sorted(legacy_executed - v2_rule_ids)
    v2_only = sorted(v2_rule_ids - legacy_executed)
    overlap = sorted(legacy_executed & v2_rule_ids)

    table = Table(
        title="[bold]Migration Delta (Legacy vs Engine-Based)[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="yellow", justify="right")

    table.add_row("Legacy executed ids (evidence)", str(len(legacy_executed)))
    table.add_row("V2 rule ids (from findings)", str(len(v2_rule_ids)))
    table.add_row("Overlap", str(len(overlap)))
    table.add_row("Legacy-only", str(len(legacy_only)))
    table.add_row("V2-only", str(len(v2_only)))

    console.print(table)

    # Show a small sample for actionability (avoid spam)
    def _sample(values: list[str], n: int = 15) -> str:
        if not values:
            return "-"
        shown = values[:n]
        more = len(values) - len(shown)
        suffix = f" (+{more} more)" if more > 0 else ""
        return ", ".join(shown) + suffix

    details = Table(
        title="[bold]Migration Candidates (Samples)[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    details.add_column("Category", style="cyan")
    details.add_column("Sample ids", style="white", overflow="fold")

    details.add_row("Legacy-only (candidate to migrate)", _sample(legacy_only))
    details.add_row("V2-only (new coverage not in legacy evidence)", _sample(v2_only))

    console.print(details)
