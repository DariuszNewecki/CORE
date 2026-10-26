from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.db_sync_worker import DbSyncWorker


# ID: 73644df8-d24d-42fc-8ef4-291ca7c43fbb
async def test_DbSyncWorker_run() -> None:
    """Happy path: sync.db succeeds with ok=True."""
    core_context = MagicMock()
    worker = DbSyncWorker(core_context=core_context)
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()

    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.data = {"message": "sync complete"}

    # Patch ActionExecutor at its defining module because it is imported
    # locally inside `run()`.
    with patch("body.atomic.executor.ActionExecutor") as mock_executor_class:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)
        mock_executor_class.return_value = mock_executor

        await worker.run()

    mock_executor.execute.assert_awaited_once_with("sync.db", write=True)
    worker.post_report.assert_awaited_once_with(
        subject="sync.db.complete",
        payload={"message": "sync complete"},
    )
    worker.post_observation.assert_not_awaited()
    worker.post_heartbeat.assert_awaited_once()


# ID: 25767f0a-bac2-40bb-82c0-0f84c06df76f
async def test_DbSyncWorker() -> None:
    """A failed or raising sync.db posts an abandoned sync.db.failed, then a heartbeat."""
    core_context = MagicMock()
    worker = DbSyncWorker(core_context=core_context)
    assert worker.declaration_name == "db_sync_worker"
    assert worker._core_context is core_context
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()

    failed = MagicMock()
    failed.ok = False
    failed.data = {"error": "db unreachable"}

    with patch("body.atomic.executor.ActionExecutor") as mock_executor_class:
        mock_executor_class.return_value.execute = AsyncMock(return_value=failed)
        await worker.run()

    mock_executor_class.assert_called_once_with(core_context)
    worker.post_report.assert_not_awaited()
    worker.post_observation.assert_awaited_once_with(
        subject="sync.db.failed",
        payload={"error": "db unreachable"},
        status="abandoned",
    )
    worker.post_heartbeat.assert_awaited_once()

    worker.post_observation.reset_mock()
    worker.post_heartbeat.reset_mock()
    with patch("body.atomic.executor.ActionExecutor") as mock_executor_class:
        mock_executor_class.return_value.execute = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        await worker.run()

    worker.post_report.assert_not_awaited()
    worker.post_observation.assert_awaited_once_with(
        subject="sync.db.failed",
        payload={"error": "boom"},
        status="abandoned",
    )
    worker.post_heartbeat.assert_awaited_once()
