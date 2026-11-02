from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.commit_authorship_audit_worker import CommitAuthorshipAuditWorker


# ID: a33e7320-21dc-46e5-856c-6a075b4514c1
def test_CommitAuthorshipAuditWorker_run():
    worker = CommitAuthorshipAuditWorker(core_context=MagicMock())

    # Async mocks for inherited worker methods
    worker.post_heartbeat = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()

    # Internal audit helper methods
    worker._audit_finalization_integrity = AsyncMock(return_value=(0, 0))
    worker._audit_consequence_evidence_degraded = AsyncMock(return_value=(0, 0))

    # Entry with declared production and no extra paths -> no violation
    entry = {
        "proposal_id": "prop-1",
        "pre_execution_sha": "sha-a",
        "post_execution_sha": "sha-b",
        "declared_production": ["src/foo.py"],
    }

    # Consequence log service
    consequence_svc = MagicMock()
    consequence_svc.get_recent_for_audit = AsyncMock(return_value=[entry])

    # Git service
    git_service = MagicMock()
    git_service.diff_file_names_for_commit = AsyncMock(return_value=["src/foo.py"])

    worker._core_context.git_service = git_service
    worker._core_context.registry = MagicMock()
    worker._core_context.registry.get_consequence_log_service = AsyncMock(
        return_value=consequence_svc
    )

    # Blackboard service
    blackboard_service = MagicMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    fake_registry = MagicMock()
    fake_registry.get_blackboard_service = AsyncMock(return_value=blackboard_service)

    with patch(
        "body.services.service_registry.service_registry",
        fake_registry,
    ):
        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    consequence_svc.get_recent_for_audit.assert_awaited_once_with(lookback_days=7)
    git_service.diff_file_names_for_commit.assert_awaited_once_with("sha-b")
    worker.post_observation.assert_not_awaited()

    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "commit_authorship_audit_worker.run.complete"
    payload = report_kwargs["payload"]
    assert payload["checked"] == 1
    assert payload["violations_detected"] == 0
    assert payload["suppressed"] == 0
