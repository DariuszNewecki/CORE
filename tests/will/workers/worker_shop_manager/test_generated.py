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





# ID: 0acb9420-8aca-4cbd-bc69-db60208eb5c4
async def test_WorkerShopManager() -> None:
    worker = WorkerShopManager()

    # Mock worker async IO boundary methods
    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    # Build a minimal schedule state where one worker is over threshold
    schedule_state = MagicMock()
    schedule_state.active_uuids = frozenset({"uuid-1"})
    schedule_state.thresholds = {"uuid-1": 60}

    registered_workers = [
        {
            "worker_name": "silent_worker",
            "worker_uuid": "uuid-1",
            "seconds_silent": 120,
        }
    ]

    existing_findings: dict[str, str] = {}

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(return_value=[])
    blackboard_svc.resolve_entries = AsyncMock()

    worker_registry_svc = MagicMock()
    worker_registry_svc.fetch_registered_workers = AsyncMock(
        return_value=registered_workers
    )

    fake_registry = MagicMock()
    fake_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)
    fake_registry.get_worker_registry_service = AsyncMock(
        return_value=worker_registry_svc
    )

    with (
        patch("body.services.service_registry.service_registry", fake_registry),
        patch(
            "will.workers.worker_shop_manager.load_worker_schedule_state",
            return_value=schedule_state,
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    worker.post_finding.assert_awaited_once()

    call_kwargs = worker.post_finding.call_args.kwargs
    assert call_kwargs["subject"] == "worker.silent::uuid-1"
    assert call_kwargs["payload"]["worker_uuid"] == "uuid-1"
    assert call_kwargs["payload"]["seconds_silent"] == 120
    assert call_kwargs["resolution_mechanism"] == "self_resolve"
