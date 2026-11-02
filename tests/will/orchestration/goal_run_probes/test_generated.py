from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: c2e7bbe3-4beb-428c-8885-774817193383
async def test_run_and_record_probes():
    from will.orchestration.goal_run_probes import run_and_record_probes

    worker = MagicMock()
    worker._context = MagicMock()
    worker.goal = "some-goal"
    worker.workflow_type = "goal_run"
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.probe_records = None

    records = [
        {"probe": "alpha", "passed": True},
        {"probe": "beta", "passed": True},
    ]

    with (
        patch(
            "will.orchestration.goal_run_probes.run_apparatus_probes",
            new=AsyncMock(return_value=records),
        ) as mock_run_probes,
        patch(
            "will.orchestration.goal_run_probes.blackboard_safe",
            side_effect=lambda r: r,
        ),
    ):
        result = await run_and_record_probes(worker, "run-123")

    assert result is True
    mock_run_probes.assert_awaited_once_with(worker._context, "run-123")
    assert worker.probe_records == records
    assert worker.post_report.await_count == 2
    worker.post_observation.assert_not_awaited()
