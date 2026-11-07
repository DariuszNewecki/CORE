from __future__ import annotations


# ID: 202de141-6a80-489b-8af9-4b1a9d1daa1d
def test_CommitReachabilityAuditor():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from will.workers.commit_reachability_auditor import CommitReachabilityAuditor

    core_context = MagicMock()

    blackboard_service = MagicMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )
    blackboard_service.fetch_resolved_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )
    blackboard_service.fetch_abandoned_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    consequence_svc = MagicMock()
    # One row: reachable commit, pre != sha
    consequence_svc.get_all_shas_with_status = AsyncMock(
        return_value=[("prop-1", "pre-sha", "post-sha", "accepted")]
    )

    registry = MagicMock()
    registry.get_consequence_log_service = AsyncMock(return_value=consequence_svc)
    core_context.registry = registry

    git_service = MagicMock()
    git_service.has_commit = AsyncMock(return_value=True)
    git_service.is_commit_on_branch = AsyncMock(return_value=True)
    git_service.get_commit_meta = AsyncMock(return_value={})
    core_context.git_service = git_service

    service_registry = MagicMock()
    service_registry.get_blackboard_service = AsyncMock(return_value=blackboard_service)

    worker = CommitReachabilityAuditor(core_context)
    worker.post_heartbeat = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()

    with patch("body.services.service_registry.service_registry", service_registry):
        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    git_service.has_commit.assert_awaited_once_with("post-sha")
    git_service.is_commit_on_branch.assert_awaited_once_with("post-sha")
    worker.post_observation.assert_not_awaited()
    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["payload"]["checked"] == 1
    assert report_kwargs["payload"]["orphans_detected"] == 0


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 23164ac2-2deb-469b-b414-903139ac2838
def test_CommitReachabilityAuditor_run() -> None:
    from will.workers.commit_reachability_auditor import CommitReachabilityAuditor

    core_context = MagicMock()

    consequence_svc = MagicMock()
    consequence_svc.get_all_shas_with_status = AsyncMock(
        return_value=[
            ("prop-1", "pre-aaa", "sha-aaa", "in_progress"),
            ("prop-2", "pre-bbb", "sha-bbb", "completed"),
            ("prop-3", "sha-ccc", "sha-ccc", "in_progress"),
        ]
    )
    core_context.registry.get_consequence_log_service = AsyncMock(
        return_value=consequence_svc
    )

    git_service = MagicMock()
    git_service.has_commit = AsyncMock(return_value=True)
    git_service.is_commit_on_branch = AsyncMock(return_value=False)
    git_service.get_commit_meta = AsyncMock(return_value={"author": "alice"})
    core_context.git_service = git_service

    blackboard_service = MagicMock()
    blackboard_service.fetch_active_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )
    blackboard_service.fetch_resolved_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )
    blackboard_service.fetch_abandoned_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )
    service_registry = MagicMock()
    service_registry.get_blackboard_service = AsyncMock(return_value=blackboard_service)

    worker = CommitReachabilityAuditor(core_context)
    worker.post_heartbeat = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()

    with patch(
        "body.services.service_registry.service_registry",
        service_registry,
    ):
        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    git_service.get_commit_meta.assert_awaited()
    assert worker.post_observation.await_count == 2
    worker.post_report.assert_awaited_once()
    report_payload = worker.post_report.await_args.kwargs["payload"]
    assert report_payload["checked"] == 2
    assert report_payload["orphans_detected"] == 2
    assert report_payload["no_commit_skipped"] == 1
