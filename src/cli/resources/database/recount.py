# src/cli/resources/database/recount.py
"""``core-admin database recount`` — recount CORE's finding figures (#1114).

``core status`` (``last_7_days``) and the thesis convergence measure count
findings created, resolved and abandoned with CORE's own SQL. This reads the
finding rows themselves and counts them here, row by row, with its own
reading of the definitions, then puts both side by side. Everything runs in
one read-only snapshot, so the three answers see the same rows.

Exit codes: 0 every figure matches, 1 one differs.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from body.services.thesis.measure import convergence_counts
from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.operational_config import load_operational_config
from will.governance.inspect_runner import LAST_7_DAYS_SQL, telemetry_patterns

from .hub import app


console = Console()

_FIGURES = ("created", "resolved", "abandoned", "telemetry_excluded")


def _count(
    rows: Iterable[tuple[str, str, Any, Any, Any]],
    start: dt.datetime,
    prefixes: tuple[str, ...],
    *,
    inclusive: bool,
) -> dict[str, int]:
    """Count finding rows (subject, status, created_at, updated_at,
    resolved_at) from *start*: telemetry is a subject starting with one of
    *prefixes*, created by created_at, resolved by resolved_at, abandoned
    by updated_at."""

    def _since(moment: Any) -> bool:
        if moment is None:
            return False
        return moment >= start if inclusive else moment > start

    counts = dict.fromkeys(_FIGURES, 0)
    for subject, status, created_at, updated_at, resolved_at in rows:
        if any(subject.startswith(p) for p in prefixes):
            counts["telemetry_excluded"] += _since(created_at)
            continue
        counts["created"] += _since(created_at)
        counts["resolved"] += status == "resolved" and _since(resolved_at)
        counts["abandoned"] += status == "abandoned" and _since(updated_at)
    return counts


@app.command("recount")
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 4e0f79cd-1b83-425e-8fda-9b9fe929996b
async def database_recount(
    ctx: typer.Context,
    days: int = typer.Option(
        30, "--days", help="The thesis window: from 00:00 UTC this many days ago."
    ),
) -> None:
    """Recount findings apart from CORE's own queries and compare (#1114)."""
    _ = ctx
    prefixes = tuple(load_operational_config().blackboard.telemetry_subject_prefixes)
    async with get_session() as session:
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        now: dt.datetime = (await session.execute(text("SELECT now()"))).scalar_one()
        since = (now - dt.timedelta(days=days)).date()
        thesis_start = dt.datetime.combine(since, dt.time(), tzinfo=dt.UTC)
        week_start = now - dt.timedelta(days=7)
        rows = (
            await session.execute(
                text(
                    "SELECT subject, status, created_at, updated_at, resolved_at "
                    "FROM core.blackboard_entries WHERE entry_type = 'finding' "
                    "AND (created_at >= :s OR updated_at >= :s OR resolved_at >= :s)"
                ),
                {"s": min(thesis_start, week_start)},
            )
        ).all()
        week = (
            await session.execute(text(LAST_7_DAYS_SQL), {"t": telemetry_patterns()})
        ).one()
        thesis = await convergence_counts(session, since)

    core = {
        "status, 7 days": dict(zip(_FIGURES, (int(v or 0) for v in week), strict=True)),
        f"thesis, since {since}": thesis,
    }
    mine = {
        "status, 7 days": _count(rows, week_start, prefixes, inclusive=False),
        f"thesis, since {since}": _count(rows, thesis_start, prefixes, inclusive=True),
    }
    table = Table(title=f"Finding recount at {now:%Y-%m-%d %H:%M:%S} UTC")
    for column in ("figure", "CORE", "recount", "match"):
        table.add_column(column)
    differs = False
    for measure, counts in core.items():
        for figure in _FIGURES:
            same = counts[figure] == mine[measure][figure]
            differs |= not same
            table.add_row(
                f"{measure}: {figure}",
                str(counts[figure]),
                str(mine[measure][figure]),
                "yes" if same else "[red]NO[/red]",
            )
    console.print(table)
    if differs:
        raise typer.Exit(1)
