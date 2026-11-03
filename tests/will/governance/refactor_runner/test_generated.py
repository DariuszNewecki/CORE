from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from will.governance.refactor_runner import run_and_persist_refactor_autonomous


@pytest.mark.asyncio
# ID: 1c2f59f7-10d6-4681-8fae-2be8a70e837b
async def test_run_and_persist_refactor_autonomous(monkeypatch):
    import will.governance.refactor_runner as rr

    run_id = uuid4()
    goal = "refactor the widget module"
    write = True

    # Fake started_at row result
    started_at_value = "2024-01-01T00:00:00"
    started_at_result = MagicMock()
    started_at_result.first = MagicMock(return_value=(started_at_value,))

    # Fake proposals result
    proposal_row_1 = (str(uuid4()),)
    proposal_row_2 = (str(uuid4()),)
    proposals_result = MagicMock()
    proposals_result.all = MagicMock(return_value=[proposal_row_1, proposal_row_2])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[started_at_result, proposals_result])

    update_mock = AsyncMock()
    monkeypatch.setattr(rr, "_update_refactor_run_status", update_mock)

    develop_mock = AsyncMock(return_value=(True, "all good"))
    monkeypatch.setattr(rr, "develop_from_goal", develop_mock)

    context = MagicMock()

    await run_and_persist_refactor_autonomous(
        context,
        session,
        run_id=run_id,
        goal=goal,
        write=write,
    )

    # develop_from_goal called correctly
    develop_mock.assert_awaited_once()
    _, dev_kwargs = develop_mock.call_args
    assert dev_kwargs["goal"] == goal
    assert dev_kwargs["workflow_type"] == "refactor_modularity"
    assert dev_kwargs["write"] is write

    # Status transitions: executing -> completed
    assert update_mock.await_count == 2
    first_call = update_mock.await_args_list[0]
    assert first_call.args[2] == "executing"

    final_call = update_mock.await_args_list[1]
    assert final_call.args[2] == "completed"
    final_kwargs = final_call.kwargs
    assert final_kwargs["finished"] is True
    assert final_kwargs["error"] is None
    result = final_kwargs["result"]
    assert result["success"] is True
    assert result["message"] == "all good"
    assert result["proposal_count"] == 2
    assert result["proposal_ids"] == [proposal_row_1[0], proposal_row_2[0]]

    assert session.execute.await_count == 2
