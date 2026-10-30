from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.llm_partition_maintainer import LlmPartitionMaintainerWorker


# ID: 17e70d78-c6b2-474a-bb31-9745051ba972
async def test_LlmPartitionMaintainerWorker_run() -> None:
    core_context = MagicMock()
    worker = LlmPartitionMaintainerWorker(core_context)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_finding = AsyncMock()

    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.data = {
        "created": ["llm_exchange_log_2025_01"],
        "skipped": ["llm_exchange_log_2024_12"],
        "advance_months": 3,
    }

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=mock_result)

    with patch("body.atomic.executor.ActionExecutor", return_value=mock_executor):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    mock_executor.execute.assert_awaited_once_with(
        "log.maintain_partitions", write=True
    )
    worker.post_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once()
    report_args = worker.post_report.await_args
    assert report_args.args[0] == "log.partition_maintenance.complete"
    payload = report_args.args[1]
    assert payload["created"] == ["llm_exchange_log_2025_01"]
    assert payload["skipped"] == ["llm_exchange_log_2024_12"]
    assert payload["created_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["advance_months"] == 3
