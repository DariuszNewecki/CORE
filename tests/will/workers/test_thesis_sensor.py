"""The thesis sensor: measured once a day, a broken rule reaches the governor
the same day as one blocking finding, and Mondays keep the week's evidence."""

from __future__ import annotations

import sys
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import body.services.thesis as thesis_package
from body.services.thesis.measure import Measurement
from shared.thesis_rules import Breach, ThesisMeasures
from will.workers.thesis_sensor import ThesisSensor, guard_breaches, week_records


MONDAY = date(2026, 10, 19)


def _blackboard(active: set[str]) -> MagicMock:
    bb = MagicMock()
    bb.fetch_active_finding_subjects_by_prefix = AsyncMock(return_value=active)
    bb.adjudicate_indeterminate_findings = AsyncMock()
    return bb


async def test_a_breach_raises_one_blocking_finding() -> None:
    worker = MagicMock()
    worker.post_observation = AsyncMock()
    today = ThesisMeasures(MONDAY, 1, 0.7, 1.0, 0.9)
    found = [Breach("unverified_writes", "1 write")]
    await guard_breaches(worker, _blackboard(set()), today, found)
    call = worker.post_observation.await_args.kwargs
    assert call["subject"] == "thesis.broken::unverified_writes"
    assert call["status"] == "indeterminate"
    assert call["payload"]["severity"] == "block"
    worker.post_observation.reset_mock()
    await guard_breaches(
        worker, _blackboard({"thesis.broken::unverified_writes"}), today, found
    )
    worker.post_observation.assert_not_awaited()  # never a second one


async def test_a_measure_that_holds_again_resolves_its_finding() -> None:
    bb = _blackboard({"thesis.broken::ai_share", "thesis.broken::convergence"})
    today = ThesisMeasures(MONDAY, 0, 0.7, 1.0, None)  # convergence unreadable
    await guard_breaches(MagicMock(), bb, today, [])
    prefixes = [
        c.kwargs["subject_prefix"]
        for c in bb.adjudicate_indeterminate_findings.await_args_list
    ]
    assert prefixes == ["thesis.broken::ai_share"]  # unreadable is not "holds"


def test_week_records_take_the_week_that_ended() -> None:
    records = [
        {"day": "2026-10-11"},
        {"day": "2026-10-12"},
        {"day": "2026-10-18"},
        {"day": "2026-10-19"},
    ]
    week, days = week_records(records, MONDAY)
    assert week == "2026-W42"
    assert [d["day"] for d in days] == ["2026-10-12", "2026-10-18"]


def _sensor() -> ThesisSensor:
    with patch("shared.workers.base.Worker.__init__", return_value=None):
        sensor = ThesisSensor(MagicMock())
    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor.post_observation = AsyncMock()
    sensor._core_context.registry.get_blackboard_service = AsyncMock(
        return_value=_blackboard(set())
    )
    return sensor


def _runtime(records: list[dict], weeks: set[str] = frozenset()) -> MagicMock:
    rt = MagicMock()
    rt.daily_records = AsyncMock(return_value=records)
    rt.evidence_weeks = AsyncMock(return_value=set(weeks))
    rt.measure_today = AsyncMock(
        return_value=Measurement(ThesisMeasures(MONDAY, 2, 0.7, 1.0, 0.9))
    )
    rt.push_week = AsyncMock(return_value="sha")
    return rt


async def _run(sensor: ThesisSensor, rt: MagicMock, today: date = MONDAY) -> None:
    clock = MagicMock()
    clock.now.return_value.date.return_value = today
    with (
        patch.dict(sys.modules, {"body.services.thesis.runtime": rt}),
        patch.object(thesis_package, "runtime", rt, create=True),
        patch("will.workers.thesis_sensor.datetime", clock),
    ):
        await sensor.run()


async def test_measures_once_a_day_and_raises_the_same_day() -> None:
    sensor, rt = _sensor(), _runtime([])
    await _run(sensor, rt, today=date(2026, 10, 20))
    rt.measure_today.assert_awaited_once()
    subjects = [c.kwargs["subject"] for c in sensor.post_report.await_args_list]
    assert subjects == ["thesis.measures::2026-10-20"]
    assert sensor.post_observation.await_args.kwargs["subject"] == (
        "thesis.broken::unverified_writes"
    )

    sensor2, rt2 = _sensor(), _runtime([{"day": "2026-10-20"}])
    await _run(sensor2, rt2, today=date(2026, 10, 20))
    rt2.measure_today.assert_not_awaited()


async def test_monday_pushes_last_week_once() -> None:
    sensor, rt = _sensor(), _runtime([{"day": "2026-10-13", "line": "x"}])
    await _run(sensor, rt)
    rt.push_week.assert_awaited_once()
    assert rt.push_week.await_args.args[0] == "2026-W42"
    assert "thesis.evidence::2026-W42" in [
        c.kwargs["subject"] for c in sensor.post_report.await_args_list
    ]

    sensor2, rt2 = _sensor(), _runtime([{"day": "2026-10-13"}], weeks={"2026-W42"})
    await _run(sensor2, rt2)
    rt2.push_week.assert_not_awaited()
