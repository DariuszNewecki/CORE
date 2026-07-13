# src/cli/commands/coverage/check_commands.py
"""
Coverage checking and reporting commands.

Thin clients over /v1/coverage/{check,report,targets,gaps} (ADR-057 D1).
Rich rendering stays here; data fetching goes through CoreApiClient.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.infrastructure.intent.operational_config import load_operational_config


logger = logging.getLogger(__name__)
console = Console()

_CFG = load_operational_config().coverage


# ID: 72963da2-9a25-487b-92ee-0d67a6d1376d
def register_check_commands(app: typer.Typer) -> None:
    """Register coverage check and report commands."""
    app.command("check")(check_coverage)
    app.command("report")(coverage_report)
    app.command("target")(show_targets)
    app.command("gaps")(show_coverage_gaps)


@core_command(dangerous=False, requires_context=False)
# ID: cbec039a-f2aa-4fc8-9a24-d7e2ba4ef15c
async def check_coverage(ctx: typer.Context) -> None:
    """Checks current test coverage against constitutional requirements."""
    _ = ctx
    console.print(
        "[bold cyan]🔍 Checking Coverage Compliance via Constitution...[/bold cyan]\n"
    )
    client = CoreApiClient()
    payload = await client.coverage_check()
    findings = payload.get("findings", [])
    if payload.get("passed", len(findings) == 0):
        console.print(
            "[bold green]✅ Coverage meets all constitutional requirements![/bold green]"
        )
        return
    blocking = [f for f in findings if str(f.get("severity", "")).lower() == "error"]
    console.print(
        f"[bold red]❌ Found {len(findings)} Coverage Violations:[/bold red]\n"
    )
    for finding in findings:
        msg = finding.get("message", "Unknown violation")
        severity = str(finding.get("severity", "warning")).lower()
        color = "red" if severity == "error" else "yellow"
        console.print(f"  • [{color}]{severity.upper()}[/{color}] {msg}")
    if blocking:
        console.print("\n[dim]Audit FAILED due to blocking errors.[/dim]")
        raise typer.Exit(code=1)


@core_command(dangerous=False, requires_context=False)
# ID: 99932c42-c4d5-48ec-aa00-cd4beb3971e8
async def coverage_report(
    ctx: typer.Context,
    show_missing: bool = typer.Option(
        True,
        "--show-missing/--no-missing",
        help="Show line numbers of missing coverage",
    ),
    html: bool = typer.Option(False, "--html", help="Generate HTML coverage report"),
) -> None:
    """Generates a detailed coverage report served by the API."""
    _ = ctx
    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")
    client = CoreApiClient()
    payload = await client.coverage_report(show_missing=show_missing)
    if not payload.get("ok", False):
        summary = payload.get("summary") or "report generation failed"
        console.print(f"[red]{summary}[/red]")
        raise typer.Exit(code=1)
    for line in payload.get("stdout_tail", []):
        console.print(line)
    if html:
        console.print("\n[bold cyan]🌐 Generating HTML coverage report...[/bold cyan]")
        html_payload = await client.coverage_report(output_format="html")
        if not html_payload.get("ok", False):
            summary = html_payload.get("summary") or "HTML report generation failed"
            console.print(f"[red]{summary}[/red]")
            raise typer.Exit(code=1)
        html_path = html_payload.get("html_path")
        if html_path:
            console.print(f"[green]✅ HTML report written to: {html_path}/[/green]")
        else:
            console.print("[yellow]HTML report ran but no html_path returned.[/yellow]")


@core_command(dangerous=False, requires_context=False)
# ID: d0e8d322-d374-42ce-9150-70c158f05297
async def show_targets(ctx: typer.Context) -> None:
    """Shows constitutional coverage targets served by the API."""
    _ = ctx
    console.print("[bold cyan]🎯 Constitutional Coverage Targets[/bold cyan]\n")
    client = CoreApiClient()
    payload = await client.coverage_targets()
    targets = payload.get("targets") or {}
    if not targets:
        console.print("[yellow]No coverage targets reported by API.[/yellow]")
        return
    rules = targets.get("rules", targets)
    if isinstance(rules, list):
        for rule in rules:
            rule_id = rule.get("id", "")
            if "coverage" not in rule_id:
                continue
            status = "blocking" if rule.get("enforcement") == "error" else "guideline"
            console.print(f"  • [bold]{rule_id}[/bold] ({status})")
            statement = rule.get("statement")
            if statement:
                console.print(f"    [dim]{statement}[/dim]\n")
    else:
        console.print(str(targets))


@core_command(dangerous=False, requires_context=False)
# ID: f9b4da0d-deca-4641-8bf5-baa906f1ade4
async def show_coverage_gaps(
    ctx: typer.Context,
    threshold: float = typer.Option(
        _CFG.gap_threshold_pct,
        "--threshold",
        "-t",
        help="Coverage percentage below which a module is flagged.",
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum modules to show."),
) -> None:
    """Shows files/modules with insufficient coverage."""
    _ = ctx
    console.print("[bold cyan]📉 Coverage Gaps Analysis[/bold cyan]\n")
    client = CoreApiClient()
    payload = await client.coverage_gaps(threshold=threshold, limit=limit)
    gaps = payload.get("gaps", [])
    if not gaps:
        console.print("[yellow]No coverage gaps reported by API.[/yellow]")
        return

    table = Table(title=f"Modules below {threshold:.0f}% coverage")
    table.add_column("Module", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Deficit", justify="right")
    for gap in gaps:
        coverage = float(gap.get("coverage", 0))
        color = (
            "red"
            if coverage < _CFG.low_bucket_pct
            else "yellow"
            if coverage < _CFG.warn_pct
            else "green"
        )
        table.add_row(
            str(gap.get("file", "")),
            f"[{color}]{coverage:.1f}%[/{color}]",
            f"{float(gap.get('deficit', 0)):.1f}%",
        )
    console.print(table)
    console.print(f"\n[bold]Total flagged:[/bold] {payload.get('count', len(gaps))}")
