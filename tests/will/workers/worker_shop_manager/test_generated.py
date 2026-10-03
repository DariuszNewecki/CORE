from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.worker_shop_manager import WorkerShopManager


# ID: 8416c638-a456-45e8-a369-7b648717f506
async def test_WorkerShopManager_run() -> None:
    manager = WorkerShopManager()

    # Stub async helpers on the instance to avoid touching DB/registry.
    manager.post_heartbeat = AsyncMock()
    manager.post_finding = AsyncMock()
    manager.post_report = AsyncMock()
    manager._fetch_registered_workers = AsyncMock(return_value=[])
    manager._fetch_existing_findings = AsyncMock(return_value={})

    schedule_state = MagicMock()
    schedule_state.thresholds = {}
    schedule_state.active_uuids = frozenset()
    schedule_state.fallback_sec = 300

    mock_blackboard = MagicMock()
    mock_blackboard.resolve_entries = AsyncMock()
    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_blackboard)

    with (
        patch(
            "will.workers.worker_shop_manager.load_worker_schedule_state",
            return_value=schedule_state,
        ),
        patch(
            "body.services.service_registry.service_registry",
            mock_registry,
        ),
    ):
        await manager.run()

    manager.post_heartbeat.assert_awaited_once()
    manager.post_report.assert_awaited_once()
    report_kwargs = manager.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "worker_shop_manager.run.complete"
    assert report_kwargs["payload"] == {
        "workers_checked": 0,
        "flagged": 0,
        "resolved": 0,
    }
