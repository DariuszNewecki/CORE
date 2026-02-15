# src/body/cli/resources/admin/traces.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567893

import typer

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)

from .hub import app


@app.command("traces")
@core_command(dangerous=False, requires_context=False)
# ID: 63d5864d-b16c-474e-8c44-0d28083c9999
async def admin_traces_cmd(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of recent traces to show."
    ),
    session_id: str = typer.Option(
        None, "--session", "-s", help="Show specific session details."
    ),
    failures_only: bool = typer.Option(
        False, "--failures", help="Show only traces with violations."
    ),
):
    """
    Inspect autonomous decision traces.

    Provides forensics on why AI agents chose specific implementations
    or strategy pivots.
    """
    from body.cli.logic.decision_inspect_logic import (
        list_recent_traces_logic,
        show_session_trace_logic,
    )

    async with get_session() as session:
        repo = DecisionTraceRepository(session)
        if session_id:
            await show_session_trace_logic(repo, session_id, details=True)
        else:
            await list_recent_traces_logic(
                repo, limit, agent=None, failures_only=failures_only
            )
