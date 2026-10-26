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


# ID: f5ebc774-b5c0-4cd2-987b-123a4bbbcd77
async def test_ObserverWorker_run() -> None:
    """run() is one cycle in a fixed order: heartbeat, collect, log, report.

    The health-log row and the blackboard report carry the same state the
    service collected, and the health log is written before the report.
    """
    worker = ObserverWorker()
    calls: list[str] = []

    state = {
        "open_findings": 7,
        "stale_entries": 2,
        "silent_workers": 1,
        "orphaned_symbols": 0,
    }

    async def _heartbeat() -> None:
        calls.append("heartbeat")

    async def _collect(threshold: int) -> dict[str, int]:
        calls.append(f"collect:{threshold}")
        return state

    async def _write(row: dict[str, int]) -> None:
        calls.append("write_health_log")

    async def _report(**kwargs: object) -> None:
        calls.append("post_report")

    worker.post_heartbeat = AsyncMock(side_effect=_heartbeat)
    worker.post_report = AsyncMock(side_effect=_report)

    hl_svc = AsyncMock()
    hl_svc.collect_system_state = AsyncMock(side_effect=_collect)
    hl_svc.write_health_log = AsyncMock(side_effect=_write)

    with patch("body.services.service_registry.service_registry") as registry:
        registry.get_health_log_service = AsyncMock(return_value=hl_svc)
        result = await worker.run()

    from will.workers.observer_worker import _CFG

    assert result is None
    assert calls == [
        "heartbeat",
        f"collect:{_CFG.stale_threshold_seconds}",
        "write_health_log",
        "post_report",
    ]
    hl_svc.write_health_log.assert_awaited_once_with(state)
    worker.post_report.assert_awaited_once_with(
        subject="observer.situation_report", payload=state
    )
