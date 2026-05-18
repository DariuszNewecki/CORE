# src/cli/commands/coverage/analysis_commands.py
"""Coverage analysis commands - history and method comparison.

Thin client over GET /v1/coverage/history and GET /v1/coverage/methods
(ADR-057 D1). Rich rendering stays here; data fetching goes through
CoreApiClient.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()


# ID: dc3466dd-9962-4fc9-94c7-c68021ecee26
def register_analysis_commands(app: typer.Typer) -> None:
    """Register coverage analysis commands."""
    app.command("history")(coverage_history)
    app.command("compare-methods")(compare_methods_command)


@core_command(dangerous=False, requires_context=False)
# ID: e2676de4-1e05-4408-9cbe-a70795cf3417
async def coverage_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of history entries to show"
    ),
) -> None:
    """Shows coverage history and trends from the API."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.coverage_history(limit=limit)
    history = payload.get("history", [])
    if not history:
        console.print("[yellow]No coverage history found[/yellow]")
        return

    console.print("[bold]📈 Coverage History[/bold]\n")
    table = Table(box=None)
    table.add_column("Date", style="dim")
    table.add_column("Coverage", justify="right")
    table.add_column("Delta", justify="right")
    for run in history:
        delta = run.get("delta", 0)
        color = "green" if delta >= 0 else "red"
        table.add_row(
            str(run.get("timestamp", "Unknown"))[:16],
            f"{run.get('overall_percent', 0)}%",
            f"[{color}]{delta:+.1f}%[/{color}]",
        )
    console.print(table)


@core_command(dangerous=False, requires_context=False)
# ID: 76d6a0c8-0e28-4de6-be76-0630526e54c0
async def compare_methods_command(ctx: typer.Context) -> None:
    """Compare coverage generation methods served by the API."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.coverage_methods()
    methods = payload.get("methods", [])

    if not methods:
        console.print("[yellow]No methods reported by API[/yellow]")
        return

    lines: list[str] = []
    for method in methods:
        name = method.get("name", method.get("id", "(unnamed)"))
        description = method.get("description", "")
        lines.append(f"[bold]{name}[/bold]\n  {description}")
    body = "\n\n".join(lines)
    console.print(
        Panel(body, title="📊 Method Comparison", border_style="cyan", expand=False)
    )
