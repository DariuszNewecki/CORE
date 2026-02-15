# src/body/cli/commands/inspect/decisions.py
# ID: 74ed9719-6e6a-4f9f-8ef1-072fb66d1483

"""
Decision trace inspection commands.

Commands:
- inspect decisions - View and filter autonomous decision traces
"""

from __future__ import annotations

import typer

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from ._helpers import (
    _show_pattern_traces,
    _show_recent_traces,
    _show_session_trace,
    _show_statistics,
)


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
    """
    Inspect decision traces from autonomous operations.

    Examples:
        core-admin inspect decisions
        core-admin inspect decisions --session abc123
        core-admin inspect decisions --agent CodeGenerator
        core-admin inspect decisions --pattern action_pattern --stats
        core-admin inspect decisions --failures-only
    """
    async with get_session() as session:
        repo = DecisionTraceRepository(session)

        if session_id:
            await _show_session_trace(repo, session_id, details)
        elif stats:
            await _show_statistics(repo, pattern, days=recent)
        elif pattern:
            await _show_pattern_traces(repo, pattern, recent, details)
        else:
            await _show_recent_traces(repo, recent, agent, failures_only, details)


# Export commands for registration
decisions_commands = [
    {"name": "decisions", "func": decisions_cmd},
]
