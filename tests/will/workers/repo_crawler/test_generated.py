from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.repo_crawler import RepoCrawlerWorker


# ID: 837dde43-3067-4719-9314-663e668af356
async def test_RepoCrawlerWorker():
    # Arrange
    worker = RepoCrawlerWorker()

    # Mock dependencies
    mock_svc = AsyncMock()
    mock_svc.run_crawl = AsyncMock(
        return_value={
            "orphans_reaped": 3,
            "coherence_guard": {},
            "files_count": 10,
            "dirs_count": 2,
        }
    )

    mock_service_registry = MagicMock()
    mock_service_registry.get_crawl_service = AsyncMock(return_value=mock_svc)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._blackboard._post_entry = AsyncMock()

    with patch(
        "body.services.service_registry.service_registry", mock_service_registry
    ):
        # Act
        await worker.run()

    # Assert
    worker.post_heartbeat.assert_awaited_once()
    worker._blackboard._post_entry.assert_awaited_once_with(
        entry_type="finding",
        subject="coherence.repo_artifacts.drift",
        payload={
            "rule_id": "coherence.repo_artifacts.drift",
            "severity": "medium",
            "drift_class": "reaped_inline",
            "orphan_count": 3,
            "remediation": "inline-reap",
            "remediated_at": worker._blackboard._post_entry.call_args[1]["payload"][
                "remediated_at"
            ],
            "pair_id": "repo_artifacts ↔ filesystem",
        },
        status="resolved",
        resolution_mechanism="self_resolve",
    )
    worker.post_report.assert_awaited_once()
    assert worker.post_report.call_args[1]["subject"] == "repo.crawl.complete"
    assert worker.post_report.call_args[1]["payload"]["orphans_reaped"] == 3
    assert "completed_at" in worker.post_report.call_args[1]["payload"]


# ID: faff67f3-13b0-4406-b7b7-c558339ae8cc
async def test_RepoCrawlerWorker_run():
    """A tripped guard posts an open human finding; a clean crawl posts none."""
    cognitive = MagicMock()
    worker = RepoCrawlerWorker(cognitive_service=cognitive)
    worker._repo_root = "/fake/repo"
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._blackboard._post_entry = AsyncMock()

    guard = {
        "triggered": True,
        "trigger": "reap_hard_cap",
        "proposed_reaps": 500,
        "total_known": 1000,
        "total_walked": 400,
        "sample_paths": ["src/x.py"],
    }
    mock_svc = AsyncMock()
    mock_svc.run_crawl = AsyncMock(
        return_value={"orphans_reaped": 0, "coherence_guard": guard}
    )
    mock_registry = MagicMock()
    mock_registry.get_crawl_service = AsyncMock(return_value=mock_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    mock_svc.run_crawl.assert_awaited_once_with("/fake/repo", cognitive)
    worker._blackboard._post_entry.assert_awaited_once()
    entry = worker._blackboard._post_entry.await_args.kwargs
    assert entry["entry_type"] == "finding"
    assert entry["subject"] == "coherence.repo_artifacts.drift"
    assert entry["status"] == "open"
    assert entry["resolution_mechanism"] == "human"
    assert entry["payload"]["severity"] == "high"
    assert entry["payload"]["remediation"] == "skipped"
    assert entry["payload"]["proposed_reaps"] == 500
    assert entry["payload"]["sample_paths"] == ["src/x.py"]
    assert worker.post_report.await_args.kwargs["subject"] == "repo.crawl.complete"

    # Nothing reaped, no guard: only the report, no drift finding.
    worker._blackboard._post_entry.reset_mock()
    worker.post_report.reset_mock()
    mock_svc.run_crawl = AsyncMock(
        return_value={"orphans_reaped": 0, "coherence_guard": None, "files": 7}
    )
    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    worker._blackboard._post_entry.assert_not_awaited()
    payload = worker.post_report.await_args.kwargs["payload"]
    assert payload["files"] == 7
    assert payload["orphans_reaped"] == 0
    assert "completed_at" in payload
