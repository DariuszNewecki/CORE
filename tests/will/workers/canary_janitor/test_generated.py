from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.canary_janitor import CanaryJanitorWorker as _CanaryJanitorWorker


# ID: e05ce365-775d-4ac7-852a-bcc327e5f124
async def test_CanaryJanitorWorker_run():
    instance = _CanaryJanitorWorker.__new__(_CanaryJanitorWorker)
    instance._canary_root = Path("/repo/work/canary")
    instance._file_service = MagicMock()
    instance.post_heartbeat = AsyncMock()
    instance.post_report = AsyncMock()

    stale_a = SimpleNamespace(path=Path("/repo/work/canary/a"), size_bytes=100)
    stale_b = SimpleNamespace(path=Path("/repo/work/canary/b"), size_bytes=50)

    with (
        patch(
            "will.workers.canary_janitor.find_stale_sandboxes",
            return_value=[stale_a, stale_b],
        ) as mock_find,
        patch(
            "will.workers.canary_janitor._reap",
            side_effect=lambda c, fs: True,
        ) as mock_reap,
        patch(
            "will.workers.canary_janitor.time.time",
            return_value=1234.5,
        ),
        patch(
            "will.workers.canary_janitor.MAX_REAP_PER_RUN",
            10,
        ),
        patch(
            "will.workers.canary_janitor.RETENTION_SECONDS",
            3600,
        ),
    ):
        await instance.run()

    mock_find.assert_called_once_with(instance._canary_root, now_ts=1234.5)
    assert mock_reap.call_count == 2
    instance.post_heartbeat.assert_awaited_once()
    instance.post_report.assert_awaited_once()

    report_args = instance.post_report.await_args.args
    assert report_args[0] == "canary_janitor.reap"
    payload = report_args[1]
    assert payload["mode"] == "delete"
    assert payload["reap_candidates"] == 2
    assert payload["reaped"] == 2
    assert payload["failed"] == 0
    assert payload["reclaimed_bytes"] == 150
    assert payload["sample"] == ["a", "b"]




# ID: 58dc9ca3-7479-4227-99dc-b9e1e488e4c2
def test_CanaryJanitorWorker():
    from will.workers.canary_janitor import CanaryJanitorWorker

    worker = CanaryJanitorWorker.__new__(CanaryJanitorWorker)

    fake_root = MagicMock()
    fake_file_service = MagicMock()
    worker._canary_root = fake_root
    worker._file_service = fake_file_service
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    stale_a = MagicMock()
    stale_a.path.name = "sandbox_a"
    stale_a.size_bytes = 100
    stale_b = MagicMock()
    stale_b.path.name = "sandbox_b"
    stale_b.size_bytes = 200

    with (
        patch(
            "will.workers.canary_janitor.find_stale_sandboxes",
            return_value=[stale_a, stale_b],
        ) as mock_find,
        patch(
            "will.workers.canary_janitor.time.time",
            return_value=1234567890.0,
        ),
        patch(
            "will.workers.canary_janitor._reap",
            return_value=True,
        ) as mock_reap,
    ):
        import asyncio

        asyncio.run(worker.run())

    mock_find.assert_called_once_with(fake_root, now_ts=1234567890.0)
    assert mock_reap.call_count == 2
    worker.post_heartbeat.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    _, report_payload = worker.post_report.await_args.args
    assert report_payload["reaped"] == 2
    assert report_payload["reclaimed_bytes"] == 300
