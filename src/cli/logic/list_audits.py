# src/cli/logic/list_audits.py

"""
Provides functionality for the list_audits module.
"""

from __future__ import annotations

import typer
from sqlalchemy import text

from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session


@core_command(dangerous=False, requires_context=False)
# ID: 23254df2-9a4f-4195-b174-53ad4ee00af4
async def list_audits(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", help="How many to show (most recent first)"
    ),
) -> None:
    """Show recent rows from core.audit_runs."""
    stmt = text(
        """
        select run_id, started_at, source, score, verdict
        from core.audit_runs
        order by started_at desc
        limit :lim
        """
    ).bindparams(lim=limit)

    async with get_session() as session:
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        typer.echo("— no audit rows yet —")
        return

    for r in rows:
        when = r.started_at.strftime("%Y-%m-%d %H:%M:%S")
        mark = "✅" if r.verdict == "PASS" else "❌"
        score = f"{float(r.score):.3f}" if r.score is not None else "—    "
        typer.echo(
            f"{str(r.run_id)[:8]}  {when}  {r.source:<7}  "
            f"score={score}  {r.verdict:<8}  {mark}"
        )
