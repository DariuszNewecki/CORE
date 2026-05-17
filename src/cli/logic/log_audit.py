# src/cli/logic/log_audit.py

"""
Provides functionality for the log_audit module.
"""

from __future__ import annotations

import typer
from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session


# ID: 90625b7b-b201-458d-84a3-895835a005c0
async def log_audit(
    score: float = typer.Option(..., "--score", help="Audit score, e.g. 0.92"),
    passed: bool = typer.Option(
        True, "--passed/--failed", help="Mark audit as passed or failed"
    ),
    source: str = typer.Option(
        "manual", "--source", help="Source label: manual|pr|nightly"
    ),
    commit_sha: str = typer.Option(
        "", "--commit", help="Optional git commit SHA (40 chars)"
    ),
) -> None:
    """Insert one row into core.audit_runs."""

    sha = commit_sha or ""
    verdict = "PASS" if passed else "FAIL"
    stmt = text(
        """
        insert into core.audit_runs
            (source, commit_sha, score, verdict, status,
             started_at, finished_at)
        values (:source, :sha, :score, :verdict, 'completed',
                now(), now())
        returning run_id
        """
    )
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                stmt,
                dict(source=source, sha=sha, score=score, verdict=verdict),
            )
            new_run_id = result.scalar_one()

    typer.echo(
        f"📝 Logged audit run_id={new_run_id} "
        f"(source={source}, score={score}, verdict={verdict})"
    )
