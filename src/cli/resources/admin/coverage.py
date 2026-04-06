# src/cli/resources/admin/coverage.py
"""
Admin Coverage Command - Constitutional Binding Audit.
Analyzes the gap between declared laws and physical enforcement.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.logic.governance.traceability_service import GovernanceTraceabilityService
from shared.cli_utils import core_command
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)


console = Console()


@app.command("coverage")
@command_meta(
    canonical_name="admin.coverage",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    summary="Audit the binding between constitutional rules and enforcement engines.",
)
@core_command(dangerous=False, requires_context=True)
# ID: 7e425c3d-d707-4f5c-84e6-57c510cfd473
async def admin_coverage_cmd(ctx: typer.Context) -> None:
    """
    Generate a Traceability Matrix.
    Identifies 'Critical Gaps' where Blocking rules have no enforcement engine.
    """
    core_context = ctx.obj
    service = GovernanceTraceabilityService(core_context.git_service.repo_path)
    logger.info(
        "\n[bold cyan]⚖️  Audit: Constitutional Binding Analysis...[/bold cyan]\n"
    )
    report = service.generate_traceability_report()
    summary = report["summary"]
    stats = f"Total Rules: {summary['total_rules']}\nEnforced   : [green]{summary['enforced_count']}[/green]\nUnbound    : [yellow]{summary['unbound_count']}[/yellow]\nCoverage   : [bold]{summary['coverage_percent']}%[/bold]"
    console.print(Panel(stats, title="Coverage Summary", expand=False))
    if report["critical_gaps"]:
        logger.info(
            "\n[bold red]🚨 CRITICAL GAPS: Blocking Rules without Enforcement[/bold red]"
        )
        gap_table = Table(show_header=True, header_style="bold red")
        gap_table.add_column("Rule ID", style="cyan")
        gap_table.add_column("Policy Source", style="dim")
        for gap in report["critical_gaps"]:
            gap_table.add_row(gap["id"], gap["policy"])
        console.print(gap_table)
    else:
        logger.info(
            "\n[bold green]✅ No Critical Gaps: All 'Blocking' rules are bound to engines.[/bold green]"
        )
    logger.info(
        "\n[dim]Full Traceability Matrix saved to: reports/governance/traceability_matrix.json[/dim]\n"
    )
