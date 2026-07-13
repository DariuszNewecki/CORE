# tests/will/workers/test_repo_crawler_drift_finding.py
"""RepoCrawlerWorker's coherence.repo_artifacts.drift findings must carry a
valid resolution_mechanism.

entry_type='finding' rows require a non-null resolution_mechanism from the
closed set (blackboard_entry_resolution_mechanism_closed_set CHECK
constraint). Both _post_entry call sites in run() omitted it, defaulting to
None — a CheckViolationError that crashed the whole worker whenever the
guard-triggered branch fired (surfaced when #776's fix let the crawler
process far more files than before, tripping reap_too_large for the first
time in practice).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from will.workers.repo_crawler import RepoCrawlerWorker


def _make_worker() -> RepoCrawlerWorker:
    worker = RepoCrawlerWorker()
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._blackboard._post_entry = AsyncMock()
    return worker


async def test_guard_triggered_finding_uses_human_resolution_mechanism() -> None:
    """A tripped reap_too_large guard posts status=open with
    resolution_mechanism='human' — a governor must inspect before any
    destructive action."""
    worker = _make_worker()

    mock_crawl_svc = AsyncMock()
    mock_crawl_svc.run_crawl = AsyncMock(
        return_value={
            "orphans_reaped": 0,
            "coherence_guard": {
                "triggered": True,
                "trigger": "reap_too_large",
                "proposed_reaps": 197,
                "total_known": 2546,
                "total_walked": 2349,
            },
        }
    )
    mock_registry = AsyncMock()
    mock_registry.get_crawl_service = AsyncMock(return_value=mock_crawl_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    worker._blackboard._post_entry.assert_awaited_once()
    call = worker._blackboard._post_entry.await_args
    assert call.kwargs["status"] == "open"
    assert call.kwargs["resolution_mechanism"] == "human"
    assert call.kwargs["subject"] == "coherence.repo_artifacts.drift"


async def test_inline_reap_finding_uses_self_resolve_mechanism() -> None:
    """An inline reap (orphans_reaped > 0, no guard trip) posts
    status=resolved with resolution_mechanism='self_resolve'."""
    worker = _make_worker()

    mock_crawl_svc = AsyncMock()
    mock_crawl_svc.run_crawl = AsyncMock(
        return_value={"orphans_reaped": 3, "coherence_guard": {"triggered": False}}
    )
    mock_registry = AsyncMock()
    mock_registry.get_crawl_service = AsyncMock(return_value=mock_crawl_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    worker._blackboard._post_entry.assert_awaited_once()
    call = worker._blackboard._post_entry.await_args
    assert call.kwargs["status"] == "resolved"
    assert call.kwargs["resolution_mechanism"] == "self_resolve"


async def test_no_drift_no_finding_posted() -> None:
    """No guard trip and no orphans reaped: no drift finding posted."""
    worker = _make_worker()

    mock_crawl_svc = AsyncMock()
    mock_crawl_svc.run_crawl = AsyncMock(
        return_value={"orphans_reaped": 0, "coherence_guard": {"triggered": False}}
    )
    mock_registry = AsyncMock()
    mock_registry.get_crawl_service = AsyncMock(return_value=mock_crawl_svc)

    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    worker._blackboard._post_entry.assert_not_awaited()
