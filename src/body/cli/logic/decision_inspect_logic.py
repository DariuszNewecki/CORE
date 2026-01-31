# src/body/cli/logic/decision_inspect_logic.py

"""
Logic specialist for inspecting autonomous decision traces.
Handles database queries and Rich-table formatting.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from shared.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)


console = Console()


# ID: 61c1204f-cfc7-41a2-b0f1-21e5476ffb42
async def show_session_trace_logic(
    repo: DecisionTraceRepository, session_id: str, details: bool
):
    """Deep inspection of a single session."""
    trace = await repo.get_by_session_id(session_id)
    if not trace:
        console.print(f"[yellow]No trace found for session: {session_id}[/yellow]")
        return

    console.print(f"\n[bold cyan]Session: {trace.session_id}[/bold cyan]")
    console.print(f"Agent: {trace.agent_name} | Decisions: {trace.decision_count}")

    if details:
        for i, d in enumerate(trace.decisions or [], 1):
            console.print(
                f"\n[cyan]{i}. {d.get('agent')} - {d.get('decision_type')}[/cyan]"
            )
            console.print(f"   Rationale: {d.get('rationale')}")


# ID: a1ddd640-38b2-43dd-ab07-2d4b3a07423d
async def list_recent_traces_logic(
    repo: DecisionTraceRepository, limit: int, agent: str | None, failures_only: bool
):
    """Builds a summary table of recent decisions."""
    traces = await repo.get_recent(
        limit=limit, agent_name=agent, failures_only=failures_only
    )
    if not traces:
        console.print("[yellow]No traces found.[/yellow]")
        return

    table = Table(title=f"Recent Decision Traces ({len(traces)})")
    table.add_column("Session", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Decisions", justify="right")
    table.add_column("Status")

    for t in traces:
        status = "❌ Violations" if t.has_violations == "true" else "✅ Clean"
        table.add_row(t.session_id[:12], t.agent_name, str(t.decision_count), status)

    console.print(table)
