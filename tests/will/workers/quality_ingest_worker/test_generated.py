from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: 4092c52b-f26e-4177-8974-72bb02903fa8
async def test_QualityIngestWorker_run() -> None:
    from will.workers.quality_ingest_worker import QualityIngestWorker

    core_context = MagicMock()
    worker = QualityIngestWorker(core_context)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_finding = AsyncMock()

    config = MagicMock()
    config.enabled_rules = ["rule_a"]

    findings = {
        "rule_a": [
            {
                "file_path": "src/foo.py",
                "message": "some violation",
                "issue_count": 3,
                "sample_issues": ["x"],
                "tool": "ruff",
            }
        ]
    }

    worker._run_audit = AsyncMock(return_value=findings)
    worker._apply_cap = MagicMock(return_value=findings)
    worker._fetch_existing_subjects = AsyncMock(return_value=set())

    with patch(
        "will.workers.quality_ingest_worker.load_audit_ingest_config",
        return_value=config,
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker._run_audit.assert_awaited_once()
    worker._apply_cap.assert_called_once_with(findings, config)
    worker._fetch_existing_subjects.assert_awaited_once()

    worker.post_finding.assert_awaited_once()
    finding_kwargs = worker.post_finding.await_args.kwargs
    assert finding_kwargs["subject"] == "audit.violation::rule_a::src/foo.py"
    assert finding_kwargs["resolution_mechanism"] == "reaudit"
    assert finding_kwargs["payload"]["rule"] == "rule_a"
    assert finding_kwargs["payload"]["status"] == "unprocessed"

    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "quality_ingest_worker.run.complete"
    assert report_kwargs["payload"]["posted"] == 1
    assert report_kwargs["payload"]["skipped_duplicate"] == 0
    assert report_kwargs["payload"]["skipped_cap"] == 0
