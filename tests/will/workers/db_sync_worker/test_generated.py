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
