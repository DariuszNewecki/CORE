from __future__ import annotations

import sys
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

    mock_runtime = MagicMock()
    mock_runtime.daily_records = AsyncMock(return_value=list(existing_records))

    sensor._measure = AsyncMock()
    sensor._push_evidence = AsyncMock()

    with (
        patch.dict(sys.modules, {"body.services.thesis.runtime": mock_runtime}),
        patch("will.workers.thesis_sensor.datetime", mock_datetime),
    ):
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    mock_runtime.daily_records.assert_awaited_once()
    sensor._measure.assert_not_awaited()
    sensor._push_evidence.assert_not_awaited()
