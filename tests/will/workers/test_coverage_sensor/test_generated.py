from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


# ID: fbf4353b-c851-4823-81a5-57eb377caf73
async def test_TestCoverageSensor_run() -> None:
    from will.workers.test_coverage_sensor import TestCoverageSensor

    worker = TestCoverageSensor(core_context=None)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_unavailable = AsyncMock()
    worker.post_artifact_finding = AsyncMock()
    worker._load_coverage_config = MagicMock(return_value={"source_root": "src"})
    worker._scan_uncovered_files = MagicMock(return_value=["a.py", "b.py"])
    worker._fetch_existing_subjects = AsyncMock(
        return_value={"test_coverage::will::a.py"}
    )
    worker._artifact_type = "test_coverage"
    worker._rule_namespace = "will"

    await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker._load_coverage_config.assert_called_once()
    worker._scan_uncovered_files.assert_called_once()
    worker._fetch_existing_subjects.assert_awaited_once()
    worker.post_artifact_finding.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    worker.post_unavailable.assert_not_awaited()
    assert (
        worker.post_artifact_finding.await_args.kwargs["identity_key_value"] == "b.py"
    )


import asyncio
from unittest.mock import patch

from will.workers.test_coverage_sensor import TestCoverageSensor


# ID: 81687bc3-5946-4d36-b4d8-8347ec288df6
def test_TestCoverageSensor() -> None:
    blackboard_svc = MagicMock()
    blackboard_svc.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    mock_service_registry = MagicMock()
    mock_service_registry.get_blackboard_service = AsyncMock(
        return_value=blackboard_svc
    )

    with (
        patch(
            "will.workers.test_coverage_sensor.load_test_coverage_config",
            return_value={"source_root": "src"},
        ),
        patch(
            "will.workers.test_coverage_sensor.uncovered_source_files",
            return_value=["src/a.py"],
        ),
        patch(
            "body.services.service_registry.service_registry",
            mock_service_registry,
        ),
        patch.object(
            TestCoverageSensor, "post_heartbeat", new=AsyncMock()
        ) as mock_heartbeat,
        patch.object(TestCoverageSensor, "post_report", new=AsyncMock()) as mock_report,
        patch.object(
            TestCoverageSensor, "post_artifact_finding", new=AsyncMock()
        ) as mock_finding,
    ):
        worker = TestCoverageSensor.__new__(TestCoverageSensor)
        worker._artifact_type = "python"
        worker._rule_namespace = "test.coverage"
        worker._repo_root = MagicMock()
        worker._core_context = None

        asyncio.new_event_loop().run_until_complete(worker.run())

    mock_heartbeat.assert_awaited_once()
    mock_finding.assert_awaited_once()
    mock_report.assert_awaited()
