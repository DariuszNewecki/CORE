# tests/shared/workers/test_schedule__worker_liveness.py

"""worker_liveness (#1103): each registry row judged against its own schedule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from shared.workers.schedule import WorkerScheduleState, worker_liveness


STATE = WorkerScheduleState(
    thresholds={"hourly": 3600 + 360, "fast": 120 + 12},
    active_uuids=frozenset({"hourly", "fast", "unscheduled"}),
    fallback_sec=900,
    on_demand_uuids=frozenset({"goal"}),
)


@pytest.mark.parametrize(
    "uuid, silent, verdict",
    [
        ("fast", 60, "alive"),
        ("hourly", 300, "alive"),
        ("hourly", 1800, "idle"),  # quiet, but its schedule is hourly
        ("hourly", 3960, "idle"),  # exactly max_interval + glide_off
        ("hourly", 3961, "overdue"),
        ("fast", 601, "overdue"),  # past its own 132 s and the 600 s window
        ("unscheduled", 800, "idle"),  # no schedule: the fallback applies
        ("unscheduled", 901, "overdue"),
        ("hourly", None, "overdue"),  # never reported
        ("goal", 3_000_000, "on_demand"),  # never overdue
        ("test_worker_ac5856b4", 60, "retired"),  # no active declaration
    ],
)
def test_verdict(uuid: str, silent: float | None, verdict: str) -> None:
    assert worker_liveness(uuid, silent, STATE, recent_sec=600) == verdict


async def test_status_counts_workers_by_their_own_schedule() -> None:
    from will.governance import daemon_runner

    beat = datetime(2026, 10, 16, 18, 13, tzinfo=UTC)
    rows = [
        {
            "worker_uuid": u,
            "worker_name": u,
            "seconds_silent": s,
            "last_heartbeat": beat,
        }
        for u, s in [
            ("fast", 30),
            ("hourly", 1500),
            ("goal", 2_877_000),
            ("test_worker_ac5856b4", 11_337_000),
        ]
    ]
    service = AsyncMock()
    service.fetch_registered_workers.return_value = rows
    with (
        patch.object(daemon_runner, "WorkerRegistryService", return_value=service),
        patch.object(daemon_runner, "load_worker_schedule_state", return_value=STATE),
        patch.object(daemon_runner, "_default_alive_threshold_sec", return_value=600),
    ):
        status = await daemon_runner.get_status(None)

    assert {w["name"]: w["state"] for w in status["workers"]} == {
        "fast": "alive",
        "hourly": "idle",
        "goal": "on_demand",
    }
    assert status["worker_count"] == 3  # the retired test row is not a worker
    assert status["retired_rows"] == 1
    assert status["alive_count"] == 2
    assert (
        status["idle_count"],
        status["on_demand_count"],
        status["overdue_count"],
    ) == (
        1,
        1,
        0,
    )
    hourly = next(w for w in status["workers"] if w["name"] == "hourly")
    assert hourly["alive"] is True and hourly["schedule_sec"] == 3960


def test_runtime_health_labels_a_quiet_scheduled_worker_idle() -> None:
    from cli.resources.runtime import health

    quiet = datetime.now(UTC) - timedelta(seconds=1800)
    assert health._liveness_label(quiet, True, False, schedule_sec=3960) == "idle"
    assert health._liveness_label(quiet, True, False, schedule_sec=900) == "stale"
    assert health._liveness_label(quiet, True, False) == "stale"
    assert health._worker_colour(quiet, True, False, schedule_sec=3960) == "cyan"
