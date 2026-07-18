# tests/will/self_healing/test_batch_remediation_service.py

"""#813: BatchRemediationService's real defects.

(B) _process_file() constructed EnhancedSingleFileRemediationService with 2
required args missing (file_handler, repo_root) — TypeError on every file.
(A related instance) _process_file() checked a "test_result" key the
producer never returns, so every file — even genuine successes — fell
through to a generic "failed" status. Both fixed together since (B) can't
be exercised without (A)'s status-mapping being correct too.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.batch_remediation_service import BatchRemediationService


def _service() -> BatchRemediationService:
    svc = BatchRemediationService(
        cognitive_service=MagicMock(),
        auditor_context=MagicMock(),
        file_handler=MagicMock(),
        max_complexity="MODERATE",
    )
    svc.repo_root = Path("/repo")
    return svc


async def test_process_file_constructs_remediation_service_with_required_args():
    """The historical bug: EnhancedSingleFileRemediationService(...) was
    missing file_handler and repo_root — a guaranteed TypeError. Assert the
    constructor now receives both."""
    svc = _service()
    with patch(
        "will.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    ) as service_cls:
        instance = service_cls.return_value
        instance.remediate = AsyncMock(
            return_value={"status": "completed", "test_file": "tests/test_foo.py"}
        )

        await svc._process_file(Path("/repo/src/foo.py"))

        _, kwargs = service_cls.call_args
        assert kwargs["file_handler"] is svc.file_handler
        assert kwargs["repo_root"] is svc.repo_root


async def test_process_file_completed_status_maps_to_success():
    """The historical bug: a genuine "completed" result still fell through
    to {"status": "failed"} because the code checked a "test_result" key
    that never existed. Assert "completed" now maps to "success"."""
    svc = _service()
    with patch(
        "will.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    ) as service_cls:
        service_cls.return_value.remediate = AsyncMock(
            return_value={
                "status": "completed",
                "test_file": "tests/test_foo.py",
                "final_coverage": 87.5,
            }
        )

        result = await svc._process_file(Path("/repo/src/foo.py"))

        assert result["status"] == "success"
        assert result["test_file"] == "tests/test_foo.py"
        assert result["final_coverage"] == 87.5


async def test_process_file_failed_status_maps_to_failed():
    svc = _service()
    with patch(
        "will.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    ) as service_cls:
        service_cls.return_value.remediate = AsyncMock(
            return_value={"status": "failed", "error": "validation_failed_after_repairs"}
        )

        result = await svc._process_file(Path("/repo/src/foo.py"))

        assert result["status"] == "failed"
        assert result["error"] == "validation_failed_after_repairs"


async def test_process_file_skipped_status_preserved():
    svc = _service()
    with patch(
        "will.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    ) as service_cls:
        service_cls.return_value.remediate = AsyncMock(
            return_value={"status": "skipped", "reason": "complexity_filter"}
        )

        result = await svc._process_file(Path("/repo/src/foo.py"))

        assert result == {"status": "skipped", "reason": "complexity_filter"}


async def test_process_file_exception_maps_to_error():
    svc = _service()
    with patch(
        "will.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    ) as service_cls:
        service_cls.return_value.remediate = AsyncMock(side_effect=RuntimeError("boom"))

        result = await svc._process_file(Path("/repo/src/foo.py"))

        assert result["status"] == "error"
        assert "boom" in result["error"]


def test_summarize_counts_success_failed_skipped():
    svc = _service()
    results = [
        {"status": "success"},
        {"status": "success"},
        {"status": "failed", "error": "x"},
        {"status": "skipped", "reason": "y"},
    ]

    summary = svc._summarize(results)

    assert summary == {"success": 2, "failed": 1, "skipped": 1}


def test_summarize_empty_results():
    svc = _service()
    assert svc._summarize([]) == {"success": 0, "failed": 0, "skipped": 0}
