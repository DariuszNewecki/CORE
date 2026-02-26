# src/body/cli/commands/inspect_decisions.py
# Copy this entire file to: src/body/cli/commands/inspect_decisions.py

# ID: cli.commands.inspect_decisions
"""
Inspect decision traces from autonomous operations.

Constitutional Compliance:
- Observability: Makes autonomous decisions transparent
- Read-only: No mutations, just queries
- Formatted output: Rich tables for human readability
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import async_command, core_command
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

inspect_app = typer.Typer(
    help="Inspect autonomous decision traces for debugging and analysis",
    no_args_is_help=True,
)


@inspect_app.command("decisions")
@async_command
@core_command(dangerous=False, requires_context=False)
# ID: 8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b
async def inspect_decisions_cmd(
    ctx: typer.Context,
    recent: int = typer.Option(
        10,
        "--recent",
        "-n",
        help="Number of recent traces to show",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Show specific session by ID",
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Filter by agent name",
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Filter by pattern used",
    ),
    failures_only: bool = typer.Option(
        False,
        "--failures-only",
        "-f",
        help="Show only traces with violations",
    ),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Show statistics instead of traces",
    ),
    details: bool = typer.Option(
        False,
        "--details",
        "-d",
        help="Show full decision details",
    ),
):
    """
    Inspect decision traces from autonomous operations.

    Examples:
        # Show 10 most recent traces
        core-admin inspect decisions

        # Show specific session
        core-admin inspect decisions --session abc123

        # Show failures only
        core-admin inspect decisions --failures-only

        # Show CodeGenerator traces
        core-admin inspect decisions --agent CodeGenerator

        # Show pattern statistics
        core-admin inspect decisions --pattern action_pattern --stats
    """
    async with get_session() as session:
        repo = DecisionTraceRepository(session)

        # Route to appropriate handler
        if session_id:
            await _show_session_trace(repo, session_id, details)
        elif stats:
            await _show_statistics(repo, pattern, recent)
        elif pattern:
            await _show_pattern_traces(repo, pattern, recent, details)
        else:
            await _show_recent_traces(repo, recent, agent, failures_only, details)


async def _show_session_trace(
    repo: DecisionTraceRepository, session_id: str, details: bool
):
    """Show a specific session trace."""
    trace = await repo.get_by_session_id(session_id)

    if not trace:
        console.print(f"[yellow]No trace found for session: {session_id}[/yellow]")
        return

    console.print(f"\n[bold cyan]Session: {trace.session_id}[/bold cyan]")
    console.print(f"Agent: {trace.agent_name}")
    console.print(f"Goal: {trace.goal or 'none'}")
    console.print(f"Decisions: {trace.decision_count}")
    console.print(f"Created: {trace.created_at}")

    if trace.has_violations:
        console.print(f"[red]Violations: {trace.violation_count}[/red]")

    if details:
        console.print("\n[bold]Decisions:[/bold]")
        for i, decision in enumerate(trace.decisions, 1):
            console.print(
                f"\n[cyan]{i}. {decision['agent']} - {decision['decision_type']}[/cyan]"
            )
            console.print(f"  Rationale: {decision['rationale']}")
            console.print(f"  Chosen: {decision['chosen_action']}")
            console.print(f"  Confidence: {decision['confidence']:.0%}")


async def _show_recent_traces(
    repo: DecisionTraceRepository,
    limit: int,
    agent: str | None,
    failures_only: bool,
    details: bool,
):
    """Show recent traces with optional filtering."""
    traces = await repo.get_recent(
        limit=limit,
        agent_name=agent,
        failures_only=failures_only,
    )

    if not traces:
        console.print("[yellow]No traces found matching criteria[/yellow]")
        return

    table = Table(title=f"Recent Decision Traces ({len(traces)})")
    table.add_column("Session", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Decisions", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Status")
    table.add_column("Created", style="dim")

    for trace in traces:
        duration = f"{trace.duration_ms/1000:.1f}s" if trace.duration_ms else "none"
        status = "❌ Violations" if trace.has_violations == "true" else "✅ Clean"

        table.add_row(
            trace.session_id[:12],
            trace.agent_name,
            str(trace.decision_count),
            duration,
            status,
            trace.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)

    if details and traces:
        console.print("\n[dim]Showing details for most recent trace...[/dim]")
        await _show_session_trace(repo, traces[0].session_id, True)


async def _show_pattern_traces(
    repo: DecisionTraceRepository,
    pattern: str,
    limit: int,
    details: bool,
):
    """Show traces that used a specific pattern."""
    traces = await repo.get_pattern_stats(pattern, limit)

    if not traces:
        console.print(f"[yellow]No traces found using pattern: {pattern}[/yellow]")
        return

    console.print(f"\n[bold cyan]Traces using pattern: {pattern}[/bold cyan]")
    console.print(f"Found: {len(traces)} traces\n")

    violations = sum(1 for t in traces if t.has_violations == "true")
    success_rate = (len(traces) - violations) / len(traces) * 100 if traces else 0

    console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
    console.print(f"Violations: [red]{violations}[/red] / {len(traces)}\n")

    if not details:
        table = Table()
        table.add_column("Session", style="cyan")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Created", style="dim")

        for trace in traces[:20]:  # Show max 20 in table
            status = "❌" if trace.has_violations == "true" else "✅"
            table.add_row(
                trace.session_id[:12],
                trace.agent_name,
                status,
                trace.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)


async def _show_statistics(
    repo: DecisionTraceRepository, pattern: str | None, days: int = 7
):
    """Show decision trace statistics."""
    console.print(
        f"\n[bold cyan]Decision Trace Statistics (Last {days} days)[/bold cyan]\n"
    )

    # Get agent counts
    agent_counts = await repo.count_by_agent(days)

    if not agent_counts:
        console.print("[yellow]No traces found in the specified time range[/yellow]")
        return

    table = Table(title="Traces by Agent")
    table.add_column("Agent", style="cyan")
    table.add_column("Count", justify="right")

    for agent, count in sorted(agent_counts.items(), key=lambda x: x[1], reverse=True):
        table.add_row(agent, str(count))

    console.print(table)

    if pattern:
        # Show pattern-specific stats
        traces = await repo.get_pattern_stats(pattern, 1000)

        if traces:
            console.print(f"\n[bold]Pattern: {pattern}[/bold]")
            violations = sum(1 for t in traces if t.has_violations == "true")
            success_rate = (len(traces) - violations) / len(traces) * 100

            console.print(f"Total uses: {len(traces)}")
            console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
            console.print(f"Violations: [red]{violations}[/red]")
