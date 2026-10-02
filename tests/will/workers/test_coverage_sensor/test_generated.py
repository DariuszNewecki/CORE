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
