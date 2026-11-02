from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.thesis_sensor import ThesisSensor


@pytest.mark.asyncio
# ID: 61132a22-7b1e-4ccc-8461-7f2d708e31dc
async def test_ThesisSensor_run():
    sensor = ThesisSensor(core_context=MagicMock())
    sensor.post_heartbeat = AsyncMock()

    # Tuesday (weekday 1) so the Monday evidence push branch is skipped.
    fixed_now = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)

    mock_datetime = MagicMock()
    mock_datetime.now = MagicMock(return_value=fixed_now)
    mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

    today_iso = fixed_now.date().isoformat()
    existing_records = [{"day": today_iso, "value": "present"}]

    daily_records = AsyncMock(return_value=list(existing_records))

    sensor._measure = AsyncMock()
    sensor._push_evidence = AsyncMock()

    with (
        # Patch the function, not sys.modules: once another test has imported
        # the real module, `from body.services.thesis import runtime` reads
        # the package attribute and a sys.modules entry is never consulted.
        patch("body.services.thesis.runtime.daily_records", daily_records),
        patch("will.workers.thesis_sensor.datetime", mock_datetime),
    ):
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    daily_records.assert_awaited_once()
    sensor._measure.assert_not_awaited()
    sensor._push_evidence.assert_not_awaited()


from datetime import date


# ID: 7a615f71-e9ec-4e3e-b93f-55ed3080fc1e
async def test_ThesisSensor():
    core_context = MagicMock()

    with patch("will.workers.thesis_sensor.Worker.__init__", return_value=None):
        sensor = ThesisSensor(core_context)

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()

    mock_runtime = MagicMock()
    mock_runtime.daily_records = AsyncMock(return_value=[])
    mock_runtime.evidence_weeks = AsyncMock(return_value=[])

    mock_measure = AsyncMock(return_value={"day": "2024-01-01"})
    sensor._measure = mock_measure
    mock_push = AsyncMock()
    sensor._push_evidence = mock_push

    with patch("body.services.thesis.runtime", mock_runtime):
        # Monday => weekday() == 0 triggers evidence push
        with patch("will.workers.thesis_sensor.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    mock_runtime.daily_records.assert_awaited_once()
    mock_measure.assert_awaited_once()
    mock_push.assert_awaited_once()


from will.workers.thesis_sensor import week_records


# ID: c8091408-95dd-45fb-80ba-a2aac55d4627
def test_week_records() -> None:
    monday = date(2024, 3, 11)  # a Monday
    # previous week: 2024-03-04 .. 2024-03-10
    records = [
        {"day": "2024-03-04", "value": 1},
        {"day": "2024-03-07", "value": 2},
        {"day": "2024-03-10", "value": 3},
        {"day": "2024-03-11", "value": 99},  # current week, excluded
        {"day": "2024-02-28", "value": 42},  # earlier week, excluded
        {"other": "key"},  # no day, excluded
    ]

    label, filtered = week_records(records, monday)

    assert filtered == [
        {"day": "2024-03-04", "value": 1},
        {"day": "2024-03-07", "value": 2},
        {"day": "2024-03-10", "value": 3},
    ]
    assert isinstance(label, str)
    assert label.startswith("2024")
    # label should reference the previous week's start date
    assert "2024" in label


# ID: 6342ff09-85c4-4e9e-8aae-4480adcdb4ae
async def test_guard_breaches() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from will.workers.thesis_sensor import BROKEN_SUBJECT, MEASURES, guard_breaches

    # Build a breach for the first measure
    measure_name = MEASURES[0]

    class _Breach:
        def __init__(self, measure: str, message: str) -> None:
            self.measure = measure
            self.message = message

    breach = _Breach(measure=measure_name, message="measure broken")

    # Active findings: none for the broken subject, but some for a different
    # measure that currently holds again (so it should be resolved).
    other_measure = MEASURES[1] if len(MEASURES) > 1 else measure_name
    held_subject = f"{BROKEN_SUBJECT}{other_measure}"

    blackboard = MagicMock()
    blackboard.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value={held_subject}
    )
    blackboard.adjudicate_indeterminate_findings = AsyncMock(return_value=None)

    worker = MagicMock()
    worker.post_observation = AsyncMock(return_value=None)

    class _Measures:
        day = MagicMock()
        day.isoformat.return_value = "2026-10-13"

    measures = _Measures()
    # Set all measures to None except the broken one; the held one should be
    # a non-None value so it gets resolved.
    for name in MEASURES:
        setattr(measures, name, None)
    setattr(measures, measure_name, 0.0)
    setattr(measures, other_measure, 0.0)

    await guard_breaches(worker, blackboard, measures, [breach])

    # The broken measure raised exactly one observation.
    worker.post_observation.assert_awaited_once()
    kwargs = worker.post_observation.await_args.kwargs
    assert kwargs["subject"] == f"{BROKEN_SUBJECT}{measure_name}"
    assert kwargs["status"] == "indeterminate"
    assert kwargs["payload"]["severity"] == "block"
    assert kwargs["payload"]["measure"] == measure_name
    assert kwargs["payload"]["day"] == "2026-10-13"
    assert kwargs["payload"]["message"] == "measure broken"

    blackboard.fetch_active_finding_subjects_by_prefix.assert_awaited_once()

    # If the held measure differs from the broken one, it should be resolved.
    if other_measure != measure_name:
        blackboard.adjudicate_indeterminate_findings.assert_awaited_once()
        adj_kwargs = blackboard.adjudicate_indeterminate_findings.await_args.kwargs
        assert adj_kwargs["subject_prefix"] == held_subject
        assert adj_kwargs["resolved_by"] == "thesis_sensor"
        assert adj_kwargs["current_violation_subjects"] == set()
