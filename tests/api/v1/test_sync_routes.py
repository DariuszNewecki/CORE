# tests/api/v1/test_sync_routes.py

"""Unit tests for sync_routes — ADR-058 Phase 4, D2.

Covers ADR-058 verification criterion 4 (all four POST /sync/* endpoints
with write=false and write=true). Mocks the will.governance.sync_runner
facade so assertions target the route translation layer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Response

from api.v1.sync_routes import (
    SyncRequest,
    get_sync_run,
    sync_code_vectors,
    sync_dev_sync,
    sync_knowledge_graph,
    sync_vectors,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


def _mock_session_returning(new_id):
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()
    return session


@pytest.mark.parametrize(
    "handler, expected_sync_type",
    [
        (sync_knowledge_graph, "knowledge_graph"),
        (sync_vectors, "vectors"),
        (sync_code_vectors, "code_vectors"),
        (sync_dev_sync, "dev_sync"),
    ],
)
@pytest.mark.parametrize("write", [False, True])
async def test_each_sync_endpoint_dispatches_with_correct_sync_type(
    handler, expected_sync_type, write
):
    """All four sync endpoints dispatch with the expected sync_type, in both
    write=false (dry-run) and write=true modes. Closes ADR-058 V4."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 200
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    new_id = uuid4()
    session = _mock_session_returning(new_id)

    payload = SyncRequest(write=write, target=None, requested_by="api")

    out = await handler(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out["run_id"] == str(new_id)
    assert out["status"] == "pending"
    assert out["href"] == f"/v1/sync/runs/{new_id}"
    background_tasks.add_task.assert_called_once()

    # Verify the INSERT parameters carry the expected sync_type and write.
    insert_call = session.execute.await_args
    _, insert_params = insert_call.args
    assert insert_params["sync_type"] == expected_sync_type
    assert insert_params["write"] is write


async def test_get_sync_run_returns_row():
    run_id = uuid4()
    session = AsyncMock()
    row = {
        "id": run_id,
        "sync_type": "knowledge_graph",
        "write": True,
        "target": None,
        "status": "completed",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": {"ok": True, "data": {"synced": 28}},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_sync_run(run_id=run_id, session=session)
    assert out["sync_type"] == "knowledge_graph"
    assert out["write"] is True
    assert out["status"] == "completed"


async def test_get_sync_run_returns_404_when_missing():
    from fastapi import HTTPException

    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_sync_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404
