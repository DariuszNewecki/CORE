# src/mind/enforcement/log_audit.py

"""
Provides functionality for the log_audit module.
"""

from __future__ import annotations

import asyncio

import typer
from sqlalchemy import text

from body.cli.logic.common import git_commit_sha
from shared.infrastructure.database.session_manager import get_session


# ID: 90625b7b-b201-458d-84a3-895835a005c0
def log_audit(
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

    async def _run():
        sha = commit_sha or git_commit_sha()
        stmt = text(
            """
            insert into core.audit_runs (source, commit_sha, score, passed, started_at, finished_at)
            values (:source, :sha, :score, :passed, now(), now())
            returning id
            """
        )
        async with get_session() as session:
            async with session.begin():
                result = await session.execute(
                    stmt, dict(source=source, sha=sha, score=score, passed=passed)
                )
                new_id = result.scalar_one()

        typer.echo(
            f"📝 Logged audit id={new_id} (source={source}, score={score}, passed={passed})"
        )

    asyncio.run(_run())
