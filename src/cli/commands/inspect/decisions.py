# src/cli/commands/inspect/decisions.py
"""Decision trace inspection commands.

Thin client over /v1/decisions and /v1/decisions/patterns (ADR-057 D3).
Rendering is inline (the legacy `_helpers` module operated on an
ORM-shaped DecisionTraceRepository; the API payloads have a different
shape and are simpler to render in place).
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
    canonical_name="inspect.decisions",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Inspect decision traces from autonomous operations",
)
@core_command(dangerous=False, requires_context=False)
# ID: d50838a6-b4f7-4ad5-ac29-3a121f65e91d
async def decisions_cmd(
    ctx: typer.Context,
    recent: int = typer.Option(
        10, "--recent", "-n", help="Number of recent traces to show"
    ),
    session_id: str | None = typer.Option(
        None, "--session", "-s", help="Show specific session by ID"
    ),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Filter by agent name"
    ),
    pattern: str | None = typer.Option(
        None, "--pattern", "-p", help="Filter by pattern used"
    ),
    failures_only: bool = typer.Option(
        False, "--failures-only", "-f", help="Show only traces with violations"
    ),
    stats: bool = typer.Option(
        False, "--stats", help="Show statistics instead of traces"
    ),
    details: bool = typer.Option(
        False, "--details", "-d", help="Show full decision details"
    ),
) -> None:
    """Inspect decision traces via /v1/decisions."""
    _ = ctx
    _ = failures_only  # Server-side filter pending — exposed via future query arg.
    client = CoreApiClient()

    if stats:
        payload = await client.decisions_patterns(days=max(recent, 1))
        _render_patterns(payload)
        return

    list_payload = await client.decisions_list(
        session_id=session_id,
        agent=agent,
        pattern=pattern,
        limit=recent,
    )
    _render_traces(list_payload, details=details)


def _render_traces(payload: dict, *, details: bool) -> None:
    """Render the decisions list JSON returned by /v1/decisions."""
    traces = payload.get("traces", [])
    if not traces:
        console.print("[yellow]No decision traces found.[/yellow]")
        return

    console.print(f"[cyan]Found {payload.get('count', len(traces))} trace(s)[/cyan]\n")
    table = Table(title="Decision Traces")
    table.add_column("Session", style="cyan")
    table.add_column("Agent", style="magenta")
    table.add_column("Pattern", style="yellow")
    table.add_column("Outcome", style="green")
    table.add_column("Created", style="dim")
    for trace in traces:
        table.add_row(
            str(trace.get("session_id") or "")[:12],
            str(trace.get("agent_id") or ""),
            str(trace.get("pattern") or ""),
            str(trace.get("outcome") or ""),
            str(trace.get("created_at") or "")[:19],
        )
    console.print(table)

    if details:
        for trace in traces:
            console.print(f"\n[bold cyan]Session {trace.get('session_id')}[/bold cyan]")
            summary = trace.get("summary")
            if summary:
                console.print(summary)


def _render_patterns(payload: dict) -> None:
    """Render the patterns aggregate returned by /v1/decisions/patterns."""
    patterns = payload.get("patterns") or []
    if not patterns:
        console.print("[yellow]No pattern statistics found.[/yellow]")
        return

    console.print(f"[cyan]Lookback: {payload.get('days', 7)} day(s)[/cyan]\n")
    table = Table(title="Pattern Classification Stats")
    table.add_column("Pattern", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Success Rate", justify="right")
    iterable = (
        patterns.items()
        if isinstance(patterns, dict)
        else ((p.get("pattern", ""), p) for p in patterns)
    )
    for name, stats_obj in iterable:
        if isinstance(stats_obj, dict):
            count = stats_obj.get("count", 0)
            success_rate = stats_obj.get("success_rate", 0)
        else:
            count = stats_obj
            success_rate = 0
        table.add_row(str(name), str(count), f"{float(success_rate):.1f}%")
    console.print(table)


decisions_commands = [
    {"name": "decisions", "func": decisions_cmd},
]
