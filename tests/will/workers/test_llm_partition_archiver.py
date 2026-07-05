# tests/will/workers/test_llm_partition_archiver.py
"""Tests for LlmPartitionArchiverWorker (ADR-052 §gxp-retention).

Covers:
- run() posts heartbeat unconditionally.
- run() posts report on action ok=True (no archived partitions).
- run() posts report on action ok=True (with archived partitions).
- run() posts finding on executor exception.
- run() posts finding on action ok=False.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.action_types import ActionResult
from will.workers.llm_partition_archiver import LlmPartitionArchiverWorker


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_worker() -> LlmPartitionArchiverWorker:
    ctx = MagicMock()
    worker = LlmPartitionArchiverWorker(core_context=ctx)
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_finding = AsyncMock()
    return worker


def _ok_result(archived: list[str] | None = None) -> ActionResult:
    retained = archived or []
    return ActionResult(
        action_id="log.archive_partitions",
        ok=True,
        data={
            "dry_run": False,
            "retention_months": 24,
            "cutoff": "2024-07",
            "archived": retained,
            "errors": [],
            "archived_count": len(retained),
            "error_count": 0,
        },
        duration_sec=0.01,
    )


def _fail_result(errors: list[str]) -> ActionResult:
    return ActionResult(
        action_id="log.archive_partitions",
        ok=False,
        data={
            "dry_run": False,
            "retention_months": 24,
            "cutoff": "2024-07",
            "archived": [],
            "errors": errors,
            "archived_count": 0,
            "error_count": len(errors),
        },
        duration_sec=0.01,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


# ID: b6aec81e-83d9-496c-83e1-8c2f5de4a2e8
@pytest.mark.asyncio
async def test_run_posts_heartbeat_unconditionally() -> None:
    """Heartbeat is always posted, regardless of action outcome."""
    worker = _make_worker()
    with patch(
        "will.workers.llm_partition_archiver.ActionExecutor"
    ) as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=_ok_result())
        mock_executor_cls.return_value = mock_executor
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()


# ID: 7e0e2a11-5b7c-4dfe-b33f-be4c61d12a7f
@pytest.mark.asyncio
async def test_run_posts_report_on_success_no_archived() -> None:
    """Posts log.partition_archival.complete when action succeeds with nothing to archive."""
    worker = _make_worker()
    with patch(
        "will.workers.llm_partition_archiver.ActionExecutor"
    ) as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=_ok_result())
        mock_executor_cls.return_value = mock_executor
        await worker.run()

    worker.post_finding.assert_not_awaited()
    worker.post_report.assert_awaited_once()
    subject, payload = worker.post_report.call_args[0]
    assert subject == "log.partition_archival.complete"
    assert payload["archived_count"] == 0


# ID: e22cbf9f-87cb-4eb9-a4e0-dcaeba3dfb38
@pytest.mark.asyncio
async def test_run_posts_report_with_archived_partitions() -> None:
    """Archived partition names appear in the report payload."""
    worker = _make_worker()
    archived = ["llm_exchange_log_2024_01", "llm_exchange_log_2024_02"]
    with patch(
        "will.workers.llm_partition_archiver.ActionExecutor"
    ) as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=_ok_result(archived))
        mock_executor_cls.return_value = mock_executor
        await worker.run()

    _subject, payload = worker.post_report.call_args[0]
    assert payload["archived_count"] == 2
    assert set(payload["archived"]) == set(archived)


# ID: d5183de3-1b82-4dce-a01b-6bd1c07b2f7b
@pytest.mark.asyncio
async def test_run_posts_finding_on_executor_exception() -> None:
    """Posts log.partition_archival.failed finding when executor raises."""
    worker = _make_worker()
    with patch(
        "will.workers.llm_partition_archiver.ActionExecutor"
    ) as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(side_effect=RuntimeError("DB unreachable"))
        mock_executor_cls.return_value = mock_executor
        await worker.run()

    worker.post_finding.assert_awaited_once()
    subject, payload = worker.post_finding.call_args[0]
    assert subject == "log.partition_archival.failed"
    assert "DB unreachable" in payload["error"]
    worker.post_report.assert_not_awaited()


# ID: c0d7a8b2-1e7a-4bc5-8c3a-9a2d47e0e5b8
@pytest.mark.asyncio
async def test_run_posts_finding_on_action_not_ok() -> None:
    """Posts log.partition_archival.failed when action returns ok=False."""
    worker = _make_worker()
    with patch(
        "will.workers.llm_partition_archiver.ActionExecutor"
    ) as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(
            return_value=_fail_result(["llm_exchange_log_2024_01: permission denied"])
        )
        mock_executor_cls.return_value = mock_executor
        await worker.run()

    worker.post_finding.assert_awaited_once()
    subject, _ = worker.post_finding.call_args[0]
    assert subject == "log.partition_archival.failed"
    worker.post_report.assert_not_awaited()
