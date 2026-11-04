from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.var_tmp_janitor import VarTmpJanitorWorker


# ID: b7793a09-3b57-4911-8751-811b5311531d
async def test_VarTmpJanitorWorker_run() -> None:
    worker = VarTmpJanitorWorker.__new__(VarTmpJanitorWorker)
    worker._tmp_root = Path("/repo/var/tmp")
    worker._file_service = MagicMock()

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    fake_candidate = MagicMock()
    fake_candidate.size_bytes = 1024
    fake_candidate.age_days = 30.0
    fake_candidate.path.name = "stale.log"

    with (
        patch(
            "will.workers.var_tmp_janitor.find_reap_candidates",
            return_value=[fake_candidate],
        ),
        patch(
            "will.workers.var_tmp_janitor._count_entries",
            return_value=5,
        ),
        patch(
            "will.workers.var_tmp_janitor._reap",
            return_value=True,
        ),
        patch(
            "will.workers.var_tmp_janitor.time.time",
            return_value=time.time(),
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    report_name, report_payload = worker.post_report.await_args.args
    assert report_name == "var_tmp_janitor.reap"
    assert report_payload["reaped"] == 1
    assert report_payload["total_entries"] == 5
    assert report_payload["reclaimed_bytes"] == 1024
    assert report_payload["sample"] == ["stale.log"]


import pytest


@pytest.mark.asyncio
# ID: 052fd285-82d9-40d8-af5f-a7a454ff5238
async def test_VarTmpJanitorWorker():
    from pathlib import Path

    fake_repo = Path("/fake/repo")
    candidate = MagicMock()
    candidate.size_bytes = 1024
    candidate.age_days = 12.5
    candidate.path = MagicMock()
    candidate.path.name = "stale_entry"

    with (
        patch(
            "shared.infrastructure.bootstrap_registry.BootstrapRegistry"
        ) as mock_registry,
        patch("will.workers.var_tmp_janitor.FileService") as mock_file_service,
        patch(
            "will.workers.var_tmp_janitor.find_reap_candidates",
            return_value=[candidate],
        ),
        patch(
            "will.workers.var_tmp_janitor._count_entries",
            return_value=5,
        ),
        patch(
            "will.workers.var_tmp_janitor._reap",
            return_value=True,
        ) as mock_reap,
        patch("will.workers.var_tmp_janitor.time") as mock_time,
    ):
        mock_registry.get_repo_path.return_value = fake_repo
        mock_time.time.return_value = 1234567890.0

        worker = VarTmpJanitorWorker()
        worker.post_heartbeat = AsyncMock()
        worker.post_report = AsyncMock()

        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    args, _ = worker.post_report.call_args
    assert args[0] == "var_tmp_janitor.reap"
    report = args[1]
    assert report["mode"] == "delete"
    assert report["total_entries"] == 5
    assert report["reap_candidates"] == 1
    assert report["reaped"] == 1
    assert report["failed"] == 0
    assert report["reclaimed_bytes"] == 1024
    assert report["sample"] == ["stale_entry"]
    mock_reap.assert_called_once()
