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
