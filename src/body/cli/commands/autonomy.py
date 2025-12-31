# src/body/cli/commands/autonomy.py
"""
Autonomy commands - A3 autonomous operation triggers and controls.

Provides:
- core-admin autonomy analyze  # Analyze audit findings for auto-fixable violations
- core-admin autonomy propose  # (Future) Generate prioritized proposals
- core-admin autonomy run      # (Future) Execute autonomous fixes
- core-admin autonomy status   # (Future) Show autonomy system status
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from features.autonomy.audit_analyzer import analyze_audit_findings
from shared.cli_utils import core_command
from shared.config import settings


console = Console()
autonomy_app = typer.Typer(
    name="autonomy",
    help="A3 autonomous operation controls and triggers",
    no_args_is_help=True,
)


@autonomy_app.command(
    "analyze", help="Analyze audit findings for auto-fixable violations"
)
@core_command(dangerous=False)
# ID: a1a2a3a4-b1b2-c1c2-d1d2-e1e2e3e4e5e6
def analyze_command(
    ctx: typer.Context,
    findings_path: Path | None = typer.Option(
        None,
        "--findings",
        help="Path to audit findings JSON (defaults to reports/audit_findings.json)",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON instead of human-readable format",
    ),
) -> None:
    """
    Analyze audit findings to identify which violations can be automatically fixed.

    This is the first step in the A3 autonomous loop:
    1. audit runs → findings
    2. analyze → identify auto-fixable
    3. propose → prioritize and plan
    4. run → execute within constitutional bounds
    """
    console.print("[cyan]🔍 Analyzing audit findings...[/cyan]\n")

    # Run analysis
    results = analyze_audit_findings(
        findings_path=findings_path,
        repo_root=settings.REPO_PATH,
    )

    # Check status
    if results["status"] == "no_findings":
        console.print("[yellow]⚠️  No audit findings found.[/yellow]")
        console.print(
            f"   Expected at: {findings_path or 'reports/audit_findings.json'}"
        )
        console.print("\n   Run [cyan]core-admin check audit[/cyan] first")
        return

    if results["status"] == "parse_error":
        console.print(f"[red]❌ {results['message']}[/red]")
        return

    if results["status"] == "format_error":
        console.print(f"[red]❌ {results['message']}[/red]")
        return

    # JSON output
    if output_json:
        console.print(json.dumps(results, indent=2))
        return

    # Human-readable output
    total = results["total_findings"]
    fixable = results["auto_fixable_count"]
    not_fixable = results["not_fixable_count"]

    # Summary
    console.print("[bold]Analysis Results[/bold]")
    console.print(f"  Total findings: {total}")
    console.print(
        f"  Auto-fixable: [green]{fixable}[/green] ({fixable / total * 100:.1f}%)"
    )
    console.print(
        f"  Not auto-fixable: [yellow]{not_fixable}[/yellow] ({not_fixable / total * 100:.1f}%)"
    )
    console.print()

    # Table of fixable actions
    if results["summary_by_action"]:
        table = Table(title="Auto-Fixable Violations by Action")
        table.add_column("Action", style="cyan", no_wrap=True)
        table.add_column("Violations", justify="right", style="green")
        table.add_column("Files", justify="right")
        table.add_column("Risk", style="yellow")
        table.add_column("Confidence", justify="right")
        table.add_column("Description")

        for summary in results["summary_by_action"]:
            table.add_row(
                summary["action"].split(".")[-1],  # Just the action name
                str(summary["finding_count"]),
                str(summary["affected_files"]),
                summary["risk_level"],
                f"{summary['confidence'] * 100:.0f}%",
                summary["description"][:50],  # Truncate long descriptions
            )

        console.print(table)
        console.print()

    # Next steps
    if fixable > 0:
        console.print("[bold green]✅ Autonomous fixes available[/bold green]")
        console.print()
        console.print("Next steps:")
        console.print("  1. Review fixable violations above")
        console.print(
            "  2. Generate proposals: [cyan]core-admin autonomy propose[/cyan] (coming soon)"
        )
        console.print(
            "  3. Execute fixes: [cyan]core-admin autonomy run --write[/cyan] (coming soon)"
        )
    else:
        console.print("[bold yellow]⚠️  No auto-fixable violations found[/bold yellow]")
        console.print()
        console.print("All audit violations require manual review or are not yet")
        console.print("mapped to autonomous actions.")


@autonomy_app.command(
    "propose", help="Generate prioritized fix proposals (coming soon)"
)
@core_command(dangerous=False)
# ID: b2b3b4b5-c2c3-d2d3-e2e3-f2f3f4f5f6f7
def propose_command(ctx: typer.Context) -> None:
    """Generate prioritized proposals from analyzed findings."""
    console.print("[yellow]⚠️  This command is not yet implemented.[/yellow]")
    console.print()
    console.print("Coming in Phase 2 of A3 implementation:")
    console.print("  - Priority scoring (risk, effort, value)")
    console.print("  - Constitutional bounds checking")
    console.print("  - Velocity limit validation")
    console.print("  - Proposal queue generation")


@autonomy_app.command("run", help="Execute autonomous fixes (coming soon)")
@core_command(dangerous=True, confirmation=True)
# ID: c3c4c5c6-d3d4-e3e4-f3f4-a4a5a6a7a8a9
def run_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Actually execute fixes (otherwise dry-run)",
    ),
) -> None:
    """Execute autonomous fixes within constitutional bounds."""
    console.print("[yellow]⚠️  This command is not yet implemented.[/yellow]")
    console.print()
    console.print("Coming in Phase 2 of A3 implementation:")
    console.print("  - Execute proposals in priority order")
    console.print("  - Respect velocity limits (max 10/hour, 50/day)")
    console.print("  - Validate against autonomy lanes")
    console.print("  - Log all autonomous decisions")
    console.print("  - Run audit after fixes to validate")


@autonomy_app.command("status", help="Show autonomy system status (coming soon)")
@core_command(dangerous=False)
# ID: d4d5d6d7-e4e5-f4f5-a5a6-b5b6b7b8b9ba
def status_command(ctx: typer.Context) -> None:
    """Show current status of autonomy system."""
    console.print("[yellow]⚠️  This command is not yet implemented.[/yellow]")
    console.print()
    console.print("Coming soon:")
    console.print("  - Active proposals")
    console.print("  - Execution history (last 24h)")
    console.print("  - Velocity limit status")
    console.print("  - Success/failure rates")
    console.print("  - Circuit breaker status")
