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
