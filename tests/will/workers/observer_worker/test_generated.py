from __future__ import annotations

from unittest.mock import AsyncMock, patch

from will.workers.observer_worker import ObserverWorker


# ID: ab4d028c-0fb8-4dab-a911-16d6e75d03f2
async def test_ObserverWorker() -> None:
    """Happy path: one full observation cycle."""
    # Build the worker (no constructor args needed).
    worker = ObserverWorker()

    # Replace the async methods on the instance so they don't actually run.
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    # Prepare a sample state dict.
    sample_state: dict[str, int] = {
        "open_findings": 3,
        "stale_entries": 1,
        "silent_workers": 0,
        "orphaned_symbols": 2,
    }

    # Patch the *defining module* of the service_registry dependency
    # (local import inside _collect_state and _write_health_log).
    with patch(
        "body.services.service_registry.service_registry",
        new_callable=AsyncMock,
    ) as mock_registry:
        # Prepare the health-log service mock.
        mock_hl_svc = AsyncMock()
        mock_hl_svc.collect_system_state = AsyncMock(return_value=sample_state)
        mock_hl_svc.write_health_log = AsyncMock()
        mock_registry.get_health_log_service = AsyncMock(return_value=mock_hl_svc)

        # Execute the observation cycle.
        await worker.run()

    # Verify heartbeat was posted.
    worker.post_heartbeat.assert_awaited_once_with()

    # Verify the state was collected with the configured threshold.
    from will.workers.observer_worker import _CFG

    mock_hl_svc.collect_system_state.assert_awaited_once_with(
        _CFG.stale_threshold_seconds
    )

    # Verify the health log was written with the collected state.
    mock_hl_svc.write_health_log.assert_awaited_once_with(sample_state)

    # Verify the situation report was posted.
    from will.workers.observer_worker import _REPORT_SUBJECT

    worker.post_report.assert_awaited_once_with(
        subject=_REPORT_SUBJECT,
        payload=sample_state,
    )
