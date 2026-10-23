"""#1114: the hand recount agrees with CORE's own finding queries.

Against a real Postgres: rows that tell the definitions apart (telemetry,
a finding resolved long ago but updated now, an abandoned one) are added,
then the 7-day status counts, the thesis counts and the row-by-row recount
are read in one snapshot. The totals cover the whole table, whatever else
it holds; they must be equal.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from body.services.thesis.measure import convergence_counts
from cli.resources.database.recount import _FIGURES, _count
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.operational_config import load_operational_config
from will.governance.inspect_runner import LAST_7_DAYS_SQL, telemetry_patterns


pytestmark = pytest.mark.integration

_ROWS = [  # subject, status, created, updated, resolved (days ago)
    ("recount.test::open", "open", 1, 1, None),
    ("recount.test::resolved", "resolved", 2, 0, 1),
    ("recount.test::resolved_long_ago", "resolved", 40, 0, 35),
    ("recount.test::abandoned", "abandoned", 20, 3, None),
    ("loop_hold.sample::recount.test", "abandoned", 2, 1, None),
]


@pytest.fixture
async def worker_id():
    wid = uuid.uuid4()
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO core.worker_registry "
                    "(worker_uuid, worker_name, worker_class, phase) "
                    "VALUES (:w, 'test_recount_worker', 'supervision', 'audit')"
                ),
                {"w": wid},
            )
            for subject, status, created, updated, resolved in _ROWS:
                await session.execute(
                    text(
                        "INSERT INTO core.blackboard_entries (id, worker_uuid, "
                        "entry_type, phase, status, subject, payload, "
                        "resolution_mechanism, resolved_at, created_at, "
                        "updated_at, last_seen_at) VALUES (:i, :w, 'finding', "
                        "'audit', :st, :s, '{}'::jsonb, 'human', "
                        "CASE WHEN CAST(:r AS int) IS NULL THEN NULL "
                        "ELSE now() - CAST(:r AS int) * interval '1 day' END, "
                        "now() - :c * interval '1 day', "
                        "now() - :u * interval '1 day', now())"
                    ),
                    {
                        "i": uuid.uuid4(),
                        "w": wid,
                        "st": status,
                        "s": subject,
                        "c": created,
                        "u": updated,
                        "r": resolved,
                    },
                )
    yield wid
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM core.blackboard_entries WHERE worker_uuid=:w"),
                {"w": wid},
            )
            await session.execute(
                text("DELETE FROM core.worker_registry WHERE worker_uuid=:w"),
                {"w": wid},
            )


async def test_the_recount_matches_both_of_cores_figures(worker_id) -> None:
    prefixes = tuple(load_operational_config().blackboard.telemetry_subject_prefixes)
    async with get_session() as session:
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        now = (await session.execute(text("SELECT now()"))).scalar_one()
        since = (now - dt.timedelta(days=30)).date()
        start = dt.datetime.combine(since, dt.time(), tzinfo=dt.UTC)
        rows = (
            await session.execute(
                text(
                    "SELECT subject, status, created_at, updated_at, resolved_at "
                    "FROM core.blackboard_entries WHERE entry_type = 'finding'"
                )
            )
        ).all()
        week = (
            await session.execute(text(LAST_7_DAYS_SQL), {"t": telemetry_patterns()})
        ).one()
        thesis = await convergence_counts(session, since)

    assert dict(zip(_FIGURES, week, strict=True)) == _count(
        rows, now - dt.timedelta(days=7), prefixes, inclusive=False
    )
    assert thesis == _count(rows, start, prefixes, inclusive=True)
    assert week[3] >= 1 and thesis["telemetry_excluded"] >= 1
