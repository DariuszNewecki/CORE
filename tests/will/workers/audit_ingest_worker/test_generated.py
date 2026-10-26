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


# ID: 04943745-1311-49b1-abe3-51e8f11e5859
async def test_AuditIngestWorker_run():
    """run() skips already-open subjects, and reports zero without a lookup."""
    worker = AuditIngestWorker(core_context=MagicMock())
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_artifact_finding = AsyncMock()
    worker._run_audit = AsyncMock(
        return_value=[
            {
                "file_path": "src/a.py",
                "line_number": 1,
                "message": "Line 1: old",
                "severity": "error",
            },
            {
                "file_path": "src/b.py",
                "line_number": 9,
                "message": "Line 9: new",
                "severity": "warning",
            },
        ]
    )
    worker._fetch_existing_subjects = AsyncMock(
        return_value={"python::ai.prompt.model_required::src/a.py::1"}
    )

    await worker.run()

    worker.post_artifact_finding.assert_awaited_once()
    posted = worker.post_artifact_finding.await_args.kwargs
    assert posted["identity_key_value"] == "src/b.py::9"
    assert posted["payload"]["severity"] == "warning"
    worker.post_report.assert_awaited_once_with(
        subject="audit_ingest_worker.run.complete",
        payload={
            "violations_found": 2,
            "posted": 1,
            "skipped_duplicates": 1,
            "message": "Run complete. 1 findings posted, 1 duplicates skipped.",
        },
    )

    # No violations: a zero report, no dedup lookup, nothing posted.
    worker.post_report.reset_mock()
    worker.post_artifact_finding.reset_mock()
    worker._fetch_existing_subjects.reset_mock()
    worker._run_audit = AsyncMock(return_value=[])

    await worker.run()

    worker._fetch_existing_subjects.assert_not_awaited()
    worker.post_artifact_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once_with(
        subject="audit_ingest_worker.run.complete",
        payload={
            "violations_found": 0,
            "message": "No ai.prompt.model_required violations detected.",
        },
    )
