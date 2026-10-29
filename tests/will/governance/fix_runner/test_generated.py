from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.governance.fix_runner import run_and_persist_quality


# ID: 6216af36-3d79-41d1-b022-05a0e507e19f
async def test_run_and_persist_quality():
    context = MagicMock()
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    result_payload = {"ok": True, "summary": "all good"}

    mock_update = AsyncMock()
    mock_lint = AsyncMock(return_value=result_payload)

    with (
        patch("will.governance.fix_runner._update_fix_run_status", mock_update),
        patch("will.governance.fix_runner._run_quality_lint", mock_lint),
    ):
        await run_and_persist_quality(
            context,
            session,
            run_id=run_id,
            check="lint",
            params={"fix": True},
        )

    mock_lint.assert_awaited_once_with(context, fix=True)

    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[1] == run_id
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    second_call = mock_update.await_args_list[1]
    assert second_call.args[1] == run_id
    assert second_call.args[2] == "completed"
    assert second_call.kwargs.get("finished") is True
    assert second_call.kwargs.get("error") is None
    assert second_call.kwargs.get("result") == result_payload
