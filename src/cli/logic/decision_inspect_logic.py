# src/cli/logic/decision_inspect_logic.py
"""
Logic specialist for inspecting autonomous decision traces.
Handles database queries and Rich-table formatting.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console
from rich.table import Table

from body.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)


console = Console()


# ID: 832820bd-1e00-453b-979c-5ad702814e25
async def show_session_trace_logic(
    repo: DecisionTraceRepository, session_id: str, details: bool
):
    """Deep inspection of a single session."""
    trace = await repo.get_by_session_id(session_id)
    if not trace:
        logger.info("[yellow]No trace found for session: %s[/yellow]", session_id)
        return
    logger.info("\n[bold cyan]Session: %s[/bold cyan]", trace.session_id)
    logger.info("Agent: %s | Decisions: %s", trace.agent_name, trace.decision_count)
    if details:
        for i, d in enumerate(trace.decisions or [], 1):
            logger.info(
                "\n[cyan]%s. %s - %s[/cyan]", i, d.get("agent"), d.get("decision_type")
            )
            logger.info("   Rationale: %s", d.get("rationale"))


# ID: 3818285c-c8c9-4727-8792-d47371ee64f3
async def list_recent_traces_logic(
    repo: DecisionTraceRepository, limit: int, agent: str | None, failures_only: bool
):
    """Builds a summary table of recent decisions."""
    traces = await repo.get_recent(
        limit=limit, agent_name=agent, failures_only=failures_only
    )
    if not traces:
        logger.info("[yellow]No traces found.[/yellow]")
        return
    table = Table(title=f"Recent Decision Traces ({len(traces)})")
    table.add_column("Session", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Decisions", justify="right")
    table.add_column("Status")
    for t in traces:
        status = "❌ Violations" if t.has_violations == "true" else "✅ Clean"
        table.add_row(t.session_id[:12], t.agent_name, str(t.decision_count), status)
    logger.info(table)
