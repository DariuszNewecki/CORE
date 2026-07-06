from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from will.workers.test_runner_sensor import TestRunnerSensor


@pytest.mark.asyncio
# ID: c3bfda65-af8b-4d7f-ae7f-b8a476232309
async def test_TestRunnerSensor():
    worker = TestRunnerSensor()

    # Mock dependencies
    mock_bb_svc = AsyncMock()
    mock_bb_svc.fetch_open_findings.return_value = []
    mock_bb_svc.fetch_active_finding_subjects_by_prefix.return_value = set()
    mock_bb_svc.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }

    mock_config = {}

    # Patch service_registry and config loader
    with patch("body.services.service_registry.service_registry") as mock_registry:
        mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_svc)

        with patch(
            "will.workers.test_runner_sensor.load_test_coverage_config",
            return_value=mock_config,
        ):
            with patch(
                "will.workers.test_runner_sensor.uncovered_source_files",
                return_value=set(),
            ):
                # Mock heartbeat, report, and artifact_finding posting
                worker.post_heartbeat = AsyncMock()
                worker.post_report = AsyncMock()
                worker.post_artifact_finding = AsyncMock()

                await worker.run()

    # Verify happy path: no findings to process
    worker.post_heartbeat.assert_awaited_once()
    mock_bb_svc.fetch_open_findings.assert_awaited_once_with(
        prefix="python::test.coverage::%", limit=50
    )
    worker.post_report.assert_awaited_once_with(
        subject="test_runner_sensor.run.complete",
        payload={"message": "No test.coverage findings to process."},
    )
