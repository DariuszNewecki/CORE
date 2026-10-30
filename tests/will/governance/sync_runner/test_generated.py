from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.governance.sync_runner import run_and_persist_sync


# ID: 7608b0e7-a523-4cc9-9f05-588ebe17d1cf
def test_run_and_persist_sync():
    context = MagicMock()
    session = AsyncMock()
    run_id = uuid4()

    action_result = MagicMock()
    action_result.ok = True
    action_result.data = {"synced": 3}
    action_result.duration_sec = 0.42

    executor_instance = MagicMock()
    executor_instance.execute = AsyncMock(return_value=action_result)

    update_status = AsyncMock(return_value=None)

    with (
        patch("will.governance.sync_runner._update_sync_run_status", update_status),
        patch("body.atomic.executor.ActionExecutor", return_value=executor_instance),
    ):
        asyncio.run(
            run_and_persist_sync(
                context,
                session,
                run_id=run_id,
                sync_type="knowledge_graph",
                write=True,
            )
        )

    executor_instance.execute.assert_awaited_once_with("sync.db", write=True)

    # First call: executing (started=True)
    first_call = update_status.await_args_list[0]
    assert first_call.args[1] == run_id
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    # Final call: completed with result payload
    final_call = update_status.await_args_list[-1]
    assert final_call.args[1] == run_id
    assert final_call.args[2] == "completed"
    assert final_call.kwargs.get("finished") is True
    assert final_call.kwargs.get("error") is None
    result = final_call.kwargs.get("result")
    assert result["ok"] is True
    assert result["data"] == {"synced": 3}
    assert result["action_id"] == "sync.db"
