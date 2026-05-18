# src/cli/commands/inspect/patterns.py
"""Pattern classification analysis commands.

Thin client over /v1/decisions/patterns (ADR-057 D3). Previously this
command walked `reports/decisions/trace_*.json` server-side; the API now
aggregates the same data so the CLI is pure presentation.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta


logger = logging.getLogger(__name__)
console = Console()


@command_meta(
    canonical_name="inspect.patterns",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Analyze pattern classification and violations across decision traces",
)
@core_command(dangerous=False, requires_context=False)
# ID: 7c9e7493-0e47-430b-ae30-753ae0cea7c3
async def patterns_cmd(
    ctx: typer.Context,
    last: int = typer.Option(
        10, "--last", "-l", help="Lookback window in days (default: 10)"
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Filter by specific pattern (e.g., 'action_pattern')",
    ),
):
    """Analyze pattern classification via /v1/decisions/patterns."""
    _ = ctx
    console.print("\n[bold blue]🔍 Pattern Classification Analysis[/bold blue]\n")

    client = CoreApiClient()
    payload = await client.decisions_patterns(days=max(last, 1))
    patterns = payload.get("patterns") or {}

    if not patterns:
        console.print("[yellow]No pattern data found.[/yellow]")
        return

    console.print(f"[cyan]Lookback: {payload.get('days', last)} day(s)[/cyan]\n")

    table = Table(title="Pattern Classification Summary")
    table.add_column("Pattern", style="cyan")
    table.add_column("Uses", justify="right")
    table.add_column("Violations", justify="right")
    table.add_column("Success Rate", justify="right")
    table.add_column("Files", justify="right")

    iterable = (
        patterns.items()
        if isinstance(patterns, dict)
        else ((p.get("pattern", ""), p) for p in patterns)
    )
    rendered = 0
    for pattern_id, stats in iterable:
        if pattern and pattern_id != pattern:
            continue
        if isinstance(stats, dict):
            uses = int(stats.get("count", 0))
            violations = int(stats.get("violations", 0))
            files_count = int(stats.get("files", 0))
        else:
            uses, violations, files_count = int(stats or 0), 0, 0
        success_rate = (uses - violations) / uses * 100 if uses > 0 else 0
        status_color = (
            "green" if success_rate > 80 else "yellow" if success_rate > 50 else "red"
        )
        table.add_row(
            str(pattern_id),
            str(uses),
            str(violations),
            f"[{status_color}]{success_rate:.1f}%[/{status_color}]",
            str(files_count),
        )
        rendered += 1

    if rendered == 0:
        console.print("[yellow]No patterns matched filter.[/yellow]")
        return

    console.print(table)


patterns_commands = [{"name": "patterns", "func": patterns_cmd}]
