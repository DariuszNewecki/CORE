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
