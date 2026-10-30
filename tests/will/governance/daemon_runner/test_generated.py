from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.daemon_runner import get_status


# ID: 83b74bf9-cec1-4704-b21f-5fd9c40c87c4
def test_get_status():
    registered = [
        {
            "worker_uuid": "u1",
            "worker_name": "alpha",
            "worker_class": "Worker",
            "phase": "p1",
            "last_heartbeat": datetime(2024, 1, 1, 12, 0, 0),
            "seconds_silent": 5,
        },
    ]

    schedule = MagicMock()
    schedule.thresholds = {"u1": 60}
    schedule.fallback_sec = 120

    service = MagicMock()
    service.fetch_registered_workers = AsyncMock(return_value=registered)

    with (
        patch(
            "will.governance.daemon_runner.WorkerRegistryService",
            return_value=service,
        ),
        patch(
            "will.governance.daemon_runner._default_alive_threshold_sec",
            return_value=90,
        ),
        patch(
            "will.governance.daemon_runner.load_worker_schedule_state",
            return_value=schedule,
        ),
        patch(
            "will.governance.daemon_runner.worker_liveness",
            return_value="alive",
        ),
        patch(
            "will.governance.daemon_runner.ALIVE",
            "alive",
        ),
        patch(
            "will.governance.daemon_runner.IDLE",
            "idle",
        ),
        patch(
            "will.governance.daemon_runner.ON_DEMAND",
            "on_demand",
        ),
        patch(
            "will.governance.daemon_runner.OVERDUE",
            "overdue",
        ),
        patch(
            "will.governance.daemon_runner.RETIRED",
            "retired",
        ),
    ):
        result = asyncio.run(get_status(None))

    service.fetch_registered_workers.assert_awaited_once()
    assert result["available"] is True
    assert result["alive_threshold_sec"] == 90
    assert result["worker_count"] == 1
    assert result["alive_count"] == 1
    assert result["retired_rows"] == 0
    assert result["workers"][0]["uuid"] == "u1"
    assert result["workers"][0]["name"] == "alpha"
    assert result["workers"][0]["state"] == "alive"
    assert result["workers"][0]["alive"] is True
    assert result["workers"][0]["schedule_sec"] == 60
    assert result["workers"][0]["last_heartbeat"] == "2024-01-01T12:00:00"
