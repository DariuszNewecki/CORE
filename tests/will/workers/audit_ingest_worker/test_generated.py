from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.workers.audit_ingest_worker import AuditIngestWorker


# ID: 12c93c5e-43b4-42c5-86f2-9b1f0dd61511
async def test_AuditIngestWorker():
    """Test the happy path of AuditIngestWorker.run() with violations."""
    worker = AuditIngestWorker(core_context=MagicMock())

    # Mock async methods on the worker
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_artifact_finding = AsyncMock()

    # Mock _run_audit to return a violation
    violations = [
        {
            "file_path": "test.py",
            "line_number": 42,
            "message": "Line 42: direct call to 'make_request_async()' not allowed",
            "severity": "error",
        }
    ]
    worker._run_audit = AsyncMock(return_value=violations)

    # Mock _fetch_existing_subjects to return an empty set (no duplicates)
    worker._fetch_existing_subjects = AsyncMock(return_value=set())

    await worker.run()

    worker.post_heartbeat.assert_awaited_once_with()
    worker._run_audit.assert_awaited_once_with()
    worker._fetch_existing_subjects.assert_awaited_once_with()

    worker.post_artifact_finding.assert_awaited_once_with(
        artifact_type="python",
        sub_namespace="ai.prompt.model_required",
        identity_key_value="test.py::42",
        payload={
            "rule": "ai.prompt.model_required",
            "file_path": "test.py",
            "line_number": 42,
            "message": "Line 42: direct call to 'make_request_async()' not allowed",
            "severity": "error",
            "status": "unprocessed",
        },
    )

    worker.post_report.assert_awaited_once_with(
        subject="audit_ingest_worker.run.complete",
        payload={
            "violations_found": 1,
            "posted": 1,
            "skipped_duplicates": 0,
            "message": "Run complete. 1 findings posted, 0 duplicates skipped.",
        },
    )
