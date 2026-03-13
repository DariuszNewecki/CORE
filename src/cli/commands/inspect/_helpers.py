# src/cli/commands/inspect/_helpers.py
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

from shared.logger import getLogger


logger = getLogger(__name__)
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
        logger.info("[yellow]No trace found for session: %s[/yellow]", session_id)
        return
    logger.info("\n[bold cyan]Session: %s[/bold cyan]", trace.session_id)
    logger.info("Agent: %s", trace.agent_name)
    logger.info("Goal: %s", trace.goal or "none")
    logger.info("Decisions: %s", trace.decision_count)
    logger.info("Created: %s", trace.created_at)
    if _as_bool(getattr(trace, "has_violations", False)):
        logger.info("[red]Violations: %s[/red]", trace.violation_count)
    if details:
        logger.info("\n[bold]Decisions:[/bold]")
        for i, decision in enumerate(trace.decisions or [], 1):
            agent = decision.get("agent", "none")
            d_type = decision.get("decision_type", "none")
            logger.info("\n[cyan]%s. %s - %s[/cyan]", i, agent, d_type)
            logger.info("  Rationale: %s", decision.get("rationale", "none"))
            logger.info("  Chosen: %s", decision.get("chosen_action", "none"))
            confidence = decision.get("confidence")
            if isinstance(confidence, (int, float)):
                logger.info("  Confidence: %s", confidence)
            else:
                logger.info("  Confidence: none")


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
        limit=limit, agent_name=agent, failures_only=failures_only
    )
    if not traces:
        logger.info("[yellow]No traces found matching criteria[/yellow]")
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
            f"{duration_ms / 1000:.1f}s"
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
    logger.info(table)
    if details and traces:
        logger.info("\n[dim]Showing details for most recent trace...[/dim]")
        await _show_session_trace(repo, traces[0].session_id, True)


async def _show_pattern_traces(
    repo: DecisionTraceRepository, pattern: str, limit: int, details: bool
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
        logger.info("[yellow]No traces found using pattern: %s[/yellow]", pattern)
        return
    logger.info("\n[bold cyan]Traces using pattern: %s[/bold cyan]", pattern)
    logger.info("Found: %s traces\n", len(traces))
    violations = sum(1 for t in traces if _as_bool(getattr(t, "has_violations", False)))
    success_rate = (len(traces) - violations) / len(traces) * 100 if traces else 0
    logger.info("Success rate: [green]%s%[/green]", success_rate)
    logger.info("Violations: [red]%s[/red] / %s\n", violations, len(traces))
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
        logger.info(table)


async def _show_statistics(
    repo: DecisionTraceRepository, pattern: str | None, days: int = 7
) -> None:
    """
    Show decision trace statistics.

    Args:
        repo: Decision trace repository
        pattern: Optional pattern to analyze
        days: Number of days to include
    """
    logger.info(
        "\n[bold cyan]Decision Trace Statistics (Last %s days)[/bold cyan]\n", days
    )
    agent_counts = await repo.count_by_agent(days)
    if not agent_counts:
        logger.info("[yellow]No traces found in the specified time range[/yellow]")
        return
    table = Table(title="Traces by Agent")
    table.add_column("Agent", style="cyan")
    table.add_column("Count", justify="right")
    for agent_name, count in sorted(
        agent_counts.items(), key=lambda x: x[1], reverse=True
    ):
        table.add_row(agent_name, str(count))
    logger.info(table)
    if pattern:
        traces = await repo.get_pattern_stats(pattern, 1000)
        if traces:
            logger.info("\n[bold]Pattern: %s[/bold]", pattern)
            violations = sum(
                1 for t in traces if _as_bool(getattr(t, "has_violations", False))
            )
            success_rate = (
                (len(traces) - violations) / len(traces) * 100 if traces else 0
            )
            logger.info("Total uses: %s", len(traces))
            logger.info("Success rate: [green]%s%[/green]", success_rate)
            logger.info("Violations: [red]%s[/red]", violations)
        else:
            logger.info("\n[yellow]No traces found for pattern: %s[/yellow]", pattern)
