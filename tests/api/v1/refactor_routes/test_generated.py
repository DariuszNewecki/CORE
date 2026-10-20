from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from api.v1.refactor_routes import get_refactor_run


@pytest.mark.asyncio
# ID: dd414582-a49b-450a-99bc-48fac2dde627
async def test_get_refactor_run():
    run_id = uuid4()
    now = datetime.now(UTC)
    expected_row = {
        "id": run_id,
        "goal": "refactor code",
        "write": True,
        "status": "completed",
        "requested_by": "user1",
        "requested_at": now,
        "started_at": now,
        "finished_at": now,
        "result": "success",
        "error": None,
    }

    mock_mappings = MagicMock()
    mock_mappings.first.return_value = expected_row

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_refactor_run(run_id, session=mock_session)

    assert result == {
        "run_id": str(run_id),
        "goal": "refactor code",
        "write": True,
        "status": "completed",
        "requested_by": "user1",
        "requested_at": now.isoformat(),
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "result": "success",
        "error": None,
    }
    mock_session.execute.assert_awaited_once_with(ANY, {"rid": run_id})


import uuid

import pytest

from api.v1.refactor_routes import run_refactor_autonomous


@pytest.mark.asyncio
# ID: 45ba2121-7294-44ab-9f94-77e22581c85a
async def test_run_refactor_autonomous():
    run_id = uuid.uuid4()

    request = MagicMock()
    request.app.state.core_context = MagicMock()

    response = MagicMock()
    background_tasks = MagicMock()

    payload = MagicMock()
    payload.goal = "reduce module coupling"
    payload.write = True
    payload.requested_by = "tester"

    result = MagicMock()
    result.scalar_one = MagicMock(return_value=run_id)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    outcome = await run_refactor_autonomous(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    background_tasks.add_task.assert_called_once()

    assert outcome == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/refactor/runs/{run_id}",
    }
