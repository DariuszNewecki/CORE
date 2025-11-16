# src/body/cli/logic/report.py
"""
Provides functionality for the report module.
"""

from __future__ import annotations

import asyncio

import typer
from services.database.session_manager import get_session
from sqlalchemy import text


# ID: 27a79c8d-285f-4e79-8de9-a4a5cba424d4
def report() -> None:
    """Summary by source (count, pass rate, avg score)."""

    async def _run():
        stmt = text(
            """
            select
              source,
              count(*) as total,
              sum(case when passed then 1 else 0 end) as passed_count,
              round(avg(score)::numeric, 3) as avg_score
            from core.audit_runs
            group by source
            order by source
            """
        )

        async with get_session() as session:
            result = await session.execute(stmt)
            rows = result.all()

        if not rows:
            typer.echo("— no data —")
            return

        typer.echo("source   total  passed  pass_rate  avg_score")
        for r in rows:
            pass_rate = (r.passed_count / r.total) * 100.0 if r.total else 0.0
            typer.echo(
                f"{r.source:<7} {r.total:>5}  {r.passed_count:>6}   {pass_rate:>6.1f}%     {float(r.avg_score):>8.3f}"
            )

    asyncio.run(_run())
