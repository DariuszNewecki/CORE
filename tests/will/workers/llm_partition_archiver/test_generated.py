from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.llm_partition_archiver import LlmPartitionArchiverWorker


# ID: 531d2498-ac74-467d-be97-749f1b1fcd19
async def test_LlmPartitionArchiverWorker_run() -> None:
    core_context = MagicMock()
    worker = LlmPartitionArchiverWorker(core_context)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_finding = AsyncMock()

    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.data = {
        "archived": ["llm_exchange_log_2023_01", "llm_exchange_log_2023_02"],
        "retention_months": 12,
        "cutoff": "2024-01-01",
    }

    fake_executor = MagicMock()
    fake_executor.execute = AsyncMock(return_value=fake_result)

    with patch(
        "body.atomic.executor.ActionExecutor",
        return_value=fake_executor,
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    fake_executor.execute.assert_awaited_once_with("log.archive_partitions", write=True)
    worker.post_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once_with(
        "log.partition_archival.complete",
        {
            "archived": ["llm_exchange_log_2023_01", "llm_exchange_log_2023_02"],
            "archived_count": 2,
            "retention_months": 12,
            "cutoff": "2024-01-01",
        },
    )


import pytest


@pytest.mark.asyncio
# ID: a86b962d-eb68-46f9-bf16-c1b599cd916a
async def test_LlmPartitionArchiverWorker() -> None:
    core_context = MagicMock()
    worker = LlmPartitionArchiverWorker(core_context)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_finding = AsyncMock()

    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.data = {
        "archived": ["llm_exchange_log_2023_01"],
        "retention_months": 24,
        "cutoff": "2024-01-01",
    }

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=mock_result)

    with patch("body.atomic.executor.ActionExecutor", return_value=mock_executor):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    mock_executor.execute.assert_awaited_once_with("log.archive_partitions", write=True)
    worker.post_report.assert_awaited_once_with(
        "log.partition_archival.complete",
        {
            "archived": ["llm_exchange_log_2023_01"],
            "archived_count": 1,
            "retention_months": 24,
            "cutoff": "2024-01-01",
        },
    )
    worker.post_finding.assert_not_awaited()
