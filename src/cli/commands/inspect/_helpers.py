# src/body/cli/commands/inspect/_helpers.py
# ID: edbfe1ba-5b19-4bae-bc62-b6678206eb27

"""
Shared helper functions for inspect commands.

Functions used across multiple inspect modules:
- _as_bool: Normalize repository return types to boolean
- _show_session_trace: Display detailed session information
- _show_recent_traces: Tabular display of recent traces
- _show_pattern_traces: Pattern-specific trace analysis
- _show_statistics: Aggregate statistics display
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table


if TYPE_CHECKING:
    from shared.infrastructure.repositories.decision_trace_repository import (
        DecisionTraceRepository,
    )

console = Console()


def _as_bool(value: Any) -> bool:
    """
    Normalize repository return types (bool/str/int/None) into a boolean.

    Supports common representations like True/"true"/"1"/1.

    Args:
        value: Value to convert to boolean

    Returns:
        Boolean interpretation of value
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "t"}
    return bool(value)


async def _show_session_trace(
    repo: DecisionTraceRepository, session_id: str, details: bool
) -> None:
    """
    Show a specific session trace with optional details.

    Args:
        repo: Decision trace repository
        session_id: Session ID to display
        details: Show full decision details
    """
    trace = await repo.get_by_session_id(session_id)

    if not trace:
        console.print(f"[yellow]No trace found for session: {session_id}[/yellow]")
        return

    console.print(f"\n[bold cyan]Session: {trace.session_id}[/bold cyan]")
    console.print(f"Agent: {trace.agent_name}")
    console.print(f"Goal: {trace.goal or 'none'}")
    console.print(f"Decisions: {trace.decision_count}")
    console.print(f"Created: {trace.created_at}")

    if _as_bool(getattr(trace, "has_violations", False)):
        console.print(f"[red]Violations: {trace.violation_count}[/red]")

    if details:
        console.print("\n[bold]Decisions:[/bold]")
        for i, decision in enumerate(trace.decisions or [], 1):
            agent = decision.get("agent", "none")
            d_type = decision.get("decision_type", "none")
            console.print(f"\n[cyan]{i}. {agent} - {d_type}[/cyan]")
            console.print(f"  Rationale: {decision.get('rationale', 'none')}")
            console.print(f"  Chosen: {decision.get('chosen_action', 'none')}")

            confidence = decision.get("confidence")
            if isinstance(confidence, (int, float)):
                console.print(f"  Confidence: {confidence:.0%}")
            else:
                console.print("  Confidence: none")


async def _show_recent_traces(
    repo: DecisionTraceRepository,
    limit: int,
    agent: str | None,
    failures_only: bool,
    details: bool,
) -> None:
    """
    Show recent traces with optional filtering in tabular format.

    Args:
        repo: Decision trace repository
        limit: Maximum number of traces to show
        agent: Filter by agent name
        failures_only: Show only failed traces
        details: Show detailed info for most recent
    """
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
        duration_ms = getattr(trace, "duration_ms", None)
        duration = (
            f"{duration_ms/1000:.1f}s"
            if isinstance(duration_ms, (int, float))
            else "none"
        )

        has_violations = _as_bool(getattr(trace, "has_violations", False))
        status = "❌ Violations" if has_violations else "✅ Clean"

        created_at = getattr(trace, "created_at", None)
        created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "none"

        table.add_row(
            (trace.session_id or "")[:12],
            trace.agent_name or "none",
            str(getattr(trace, "decision_count", 0)),
            duration,
            status,
            created_str,
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
) -> None:
    """
    Show traces that used a specific pattern.

    Args:
        repo: Decision trace repository
        pattern: Pattern ID to filter by
        limit: Maximum number of traces
        details: Show detailed view
    """
    traces = await repo.get_pattern_stats(pattern, limit)

    if not traces:
        console.print(f"[yellow]No traces found using pattern: {pattern}[/yellow]")
        return

    console.print(f"\n[bold cyan]Traces using pattern: {pattern}[/bold cyan]")
    console.print(f"Found: {len(traces)} traces\n")

    violations = sum(1 for t in traces if _as_bool(getattr(t, "has_violations", False)))
    success_rate = (len(traces) - violations) / len(traces) * 100 if traces else 0

    console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
    console.print(f"Violations: [red]{violations}[/red] / {len(traces)}\n")

    if not details:
        table = Table()
        table.add_column("Session", style="cyan")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Created", style="dim")

        for trace in traces[:20]:
            status = "❌" if _as_bool(getattr(trace, "has_violations", False)) else "✅"
            created_at = getattr(trace, "created_at", None)
            created_str = (
                created_at.strftime("%Y-%m-%d %H:%M") if created_at else "none"
            )
            table.add_row(
                (trace.session_id or "")[:12],
                trace.agent_name or "none",
                status,
                created_str,
            )

        console.print(table)


async def _show_statistics(
    repo: DecisionTraceRepository,
    pattern: str | None,
    days: int = 7,
) -> None:
    """
    Show decision trace statistics.

    Args:
        repo: Decision trace repository
        pattern: Optional pattern to analyze
        days: Number of days to include
    """
    console.print(
        f"\n[bold cyan]Decision Trace Statistics (Last {days} days)[/bold cyan]\n"
    )

    agent_counts = await repo.count_by_agent(days)

    if not agent_counts:
        console.print("[yellow]No traces found in the specified time range[/yellow]")
        return

    table = Table(title="Traces by Agent")
    table.add_column("Agent", style="cyan")
    table.add_column("Count", justify="right")

    for agent_name, count in sorted(
        agent_counts.items(), key=lambda x: x[1], reverse=True
    ):
        table.add_row(agent_name, str(count))

    console.print(table)

    if pattern:
        traces = await repo.get_pattern_stats(pattern, 1000)

        if traces:
            console.print(f"\n[bold]Pattern: {pattern}[/bold]")
            violations = sum(
                1 for t in traces if _as_bool(getattr(t, "has_violations", False))
            )
            success_rate = (
                (len(traces) - violations) / len(traces) * 100 if traces else 0
            )

            console.print(f"Total uses: {len(traces)}")
            console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
            console.print(f"Violations: [red]{violations}[/red]")
        else:
            console.print(f"\n[yellow]No traces found for pattern: {pattern}[/yellow]")
