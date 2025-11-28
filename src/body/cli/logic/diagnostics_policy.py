# src/body/cli/logic/diagnostics_policy.py
"""
Logic for constitutional policy coverage auditing.
"""

from __future__ import annotations

from typing import Any

import typer
from mind.governance.policy_coverage_service import PolicyCoverageService
from rich.console import Console
from rich.table import Table

console = Console()


def _print_policy_coverage_summary(summary: dict[str, Any]) -> None:
    """Print a compact summary of policy coverage metrics."""
    console.print()
    console.print(
        "[bold underline]Constitutional Policy Coverage Summary[/bold underline]"
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Policies Seen", str(summary.get("policies_seen", 0)))
    table.add_row("Rules Found", str(summary.get("rules_found", 0)))
    table.add_row("Rules (direct)", str(summary.get("rules_direct", 0)))
    table.add_row("Rules (bound)", str(summary.get("rules_bound", 0)))
    table.add_row("Rules (inferred)", str(summary.get("rules_inferred", 0)))
    table.add_row("Uncovered Rules (all)", str(summary.get("uncovered_rules", 0)))
    table.add_row(
        "Uncovered ERROR Rules",
        str(summary.get("uncovered_error_rules", 0)),
    )

    console.print(table)
    console.print()


def _print_policy_coverage_table(records: list[dict[str, Any]]) -> None:
    """Show all rules with their coverage type so gaps are visible."""
    if not records:
        console.print(
            "[yellow]No policy rules discovered; nothing to display.[/yellow]"
        )
        return

    console.print("[bold underline]Policy Rules Coverage[/bold underline]")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Policy", style="bold")
    table.add_column("Rule ID")
    table.add_column("Enforcement", justify="center")
    table.add_column("Coverage", justify="center")
    table.add_column("Covered?", justify="center")

    sorted_records = sorted(
        records,
        key=lambda r: (
            not r.get("covered", False),
            r.get("policy_id", ""),
            r.get("rule_id", ""),
        ),
    )

    for rec in sorted_records:
        policy = rec.get("policy_id", "")
        rule_id = rec.get("rule_id", "")
        enforcement = rec.get("enforcement", "")
        coverage = rec.get("coverage", "none")
        covered = rec.get("covered", False)

        covered_str = "[green]Yes[/green]" if covered else "[red]No[/red]"
        table.add_row(policy, rule_id, enforcement, coverage, covered_str)

    console.print(table)
    console.print()


def _print_uncovered_policy_rules(records: list[dict[str, Any]]) -> None:
    """Only show the rules that are not covered."""
    uncovered = [r for r in records if not r.get("covered", False)]
    if not uncovered:
        return

    console.print("[bold underline]Uncovered Policy Rules[/bold underline]")

    table = Table(show_header=True, header_style="bold red")
    table.add_column("Policy")
    table.add_column("Rule ID")
    table.add_column("Enforcement", justify="center")
    table.add_column("Coverage", justify="center")

    for rec in uncovered:
        table.add_row(
            rec.get("policy_id", ""),
            rec.get("rule_id", ""),
            rec.get("enforcement", ""),
            rec.get("coverage", "none"),
        )

    console.print(table)
    console.print()


# ID: 25d4e8f9-ae1e-424e-972d-2dcb74f918b7
def policy_coverage():
    """
    Runs a meta-audit on all .intent/charter/policies/ to ensure they are
    well-formed and covered by the governance model.
    """
    console.print(
        "[bold cyan]🚀 Running Constitutional Policy Coverage Audit...[/bold cyan]"
    )
    service = PolicyCoverageService()
    report = service.run()

    console.print(f"Report ID: [dim]{report.report_id}[/dim]")

    _print_policy_coverage_summary(report.summary)
    _print_policy_coverage_table(report.records)

    if report.summary.get("uncovered_rules", 0) > 0:
        _print_uncovered_policy_rules(report.records)

    if report.exit_code != 0:
        console.print(
            f"[bold red]❌ Policy coverage audit failed with exit code: {report.exit_code}[/bold red]"
        )
        raise typer.Exit(code=report.exit_code)

    console.print(
        "[bold green]✅ All active policies are backed by implemented or inferred checks.[/bold green]"
    )
