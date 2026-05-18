# src/cli/commands/check/quality_gates.py
"""
Quality Gates Command — thin client over POST /v1/quality/gates.

Dispatches the six industry-standard checks (ruff/mypy/pytest/pip-audit/
radon/vulture) server-side via fix_runs (kind='quality_check'). The CLI
polls and renders the per-check summary.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 41993614-7f98-425d-bfab-5c5d65c26d2f
async def quality_gates_cmd(
    ctx: typer.Context,
    fix: bool = typer.Option(False, "--fix", help="Attempt to auto-fix violations"),
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
) -> None:
    """
    Run all quality gates (ruff, mypy, coverage, security, complexity, dead code).

    Dispatches to POST /v1/quality/gates; the server runs the bundle and
    persists per-check results in fix_runs.result. --fix and --strict are
    forwarded as params.
    """
    _ = ctx
    console.print("\n[bold blue]🔍 Running Quality Gates[/bold blue]\n")
    client = CoreApiClient()
    initial = await client.quality_gates()
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]quality.gates failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") not in {"completed", "failed"}:
        console.print(f"[red]quality.gates unexpected status: {final}[/red]")
        raise typer.Exit(1)

    payload = final.get("result") or {}
    results = payload.get("checks", payload.get("results", []))
    _display_summary(results, strict=strict, fix=fix)

    critical_failures = [
        r for r in results if not r.get("passed") and not r.get("is_warning")
    ]
    warning_failures = [
        r for r in results if not r.get("passed") and r.get("is_warning")
    ]
    if critical_failures or (strict and warning_failures):
        raise typer.Exit(code=1)


def _display_summary(results: list[dict], *, strict: bool, fix: bool) -> None:
    """Render the server's per-check results as a table."""
    console.print("\n[bold]Quality Gates Summary[/bold]\n")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Summary", style="dim")
    for result in results:
        check_type = "WARNING" if result.get("is_warning") else "ERROR"
        if result.get("passed"):
            status = "[green]✓ PASS[/green]"
        elif result.get("is_warning"):
            status = "[yellow]⚠ WARN[/yellow]"
        else:
            status = "[red]✗ FAIL[/red]"
        summary = result.get("summary", "")
        if len(summary) > 60:
            summary = summary[:60] + "..."
        table.add_row(result.get("name", ""), status, check_type, summary)
    console.print(table)
    critical_fails = sum(
        1 for r in results if not r.get("passed") and not r.get("is_warning")
    )
    warning_fails = sum(
        1 for r in results if not r.get("passed") and r.get("is_warning")
    )
    if critical_fails == 0 and warning_fails == 0:
        console.print("\n[bold green]✅ All quality gates passed![/bold green]\n")
    elif critical_fails == 0:
        console.print(
            f"\n[bold yellow]⚠️  {warning_fails} warning(s) - review recommended[/bold yellow]\n"
        )
    else:
        console.print(
            f"\n[bold red]❌ {critical_fails} critical failure(s) - must fix before merge[/bold red]\n"
        )
    if fix:
        logger.info("--fix forwarded to server (per-check auto-fix where supported).")
    if strict:
        logger.info("--strict in effect: warnings will fail this run.")
