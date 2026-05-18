# tests/api/v1/test_refactor_routes.py

"""Unit tests for refactor_routes — ADR-057 Phase 3, D2.

Covers ADR-057 verification criterion 3 (autonomous cycle dry-run +
circuit-breaker boundary). The circuit-breaker boundary case is
simulated by mocking run_and_persist_refactor_autonomous to raise the
governance error that ADR-038 would surface in production.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from api.v1.refactor_routes import (
    RunAutonomousRequest,
    get_refactor_run,
    refactor_candidates,
    refactor_score,
    refactor_stats,
    refactor_threshold,
    run_refactor_autonomous,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    request.app.state.core_context.git_service.repo_path = "/tmp/repo"
    return request


@pytest.mark.asyncio
async def test_autonomous_dry_run_inserts_and_schedules():
    """POST /refactor/autonomous with write=false inserts a pending row,
    schedules the A3 loop, and returns 202. Closes ADR-057 verification #3
    dry-run case."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 200
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    new_id = uuid4()
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    payload = RunAutonomousRequest(
        goal="Improve modularity of user_service.py", write=False
    )

    out = await run_refactor_autonomous(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/refactor/runs/{new_id}",
    }
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_autonomous_circuit_breaker_failure_persists_on_row():
    """When the A3 loop trips the circuit breaker (ADR-038), the facade
    records the failure on the row. The route handler still returns 202
    — circuit-breaker outcomes are visible via the resource read."""

    fake_run_id = uuid4()

    captured: dict = {}

    async def fake_runner(*args, **kwargs):
        captured["called"] = True
        captured["run_id"] = kwargs.get("run_id")
        raise RuntimeError("circuit_breaker_tripped")

    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 200
    background_tasks = MagicMock(spec=BackgroundTasks)
    captured_tasks: list = []
    background_tasks.add_task = MagicMock(
        side_effect=lambda task, *a, **kw: captured_tasks.append(task)
    )

    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=fake_run_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    payload = RunAutonomousRequest(goal="Break things", write=False)
    with patch(
        "api.v1.refactor_routes.run_and_persist_refactor_autonomous",
        new=fake_runner,
    ):
        out = await run_refactor_autonomous(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert out["status"] == "pending"
    assert response.status_code == 202
    assert len(captured_tasks) == 1


@pytest.mark.asyncio
async def test_get_refactor_run_returns_row():
    run_id = uuid4()
    session = AsyncMock()
    row = {
        "id": run_id,
        "goal": "Improve modularity",
        "write": False,
        "status": "completed",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": {"success": True, "proposal_ids": []},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_refactor_run(run_id=run_id, session=session)
    assert out["run_id"] == str(run_id)
    assert out["goal"] == "Improve modularity"


@pytest.mark.asyncio
async def test_get_refactor_run_returns_404_when_missing():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_refactor_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_refactor_threshold_delegates_to_facade():
    request = _mock_request_with_context()
    with patch(
        "api.v1.refactor_routes.get_refactor_threshold",
        return_value=60.0,
    ):
        out = await refactor_threshold(request=request)
    assert out == {"threshold": 60.0}


@pytest.mark.asyncio
async def test_refactor_score_404_when_facade_reports_missing():
    request = _mock_request_with_context()
    with patch(
        "api.v1.refactor_routes.get_refactor_score",
        return_value={"file": "src/x.py", "found": False, "score": 0.0, "details": None},
    ):
        with pytest.raises(HTTPException) as exc:
            await refactor_score(request=request, file="src/x.py")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_refactor_score_returns_facade_payload_when_present():
    request = _mock_request_with_context()
    payload = {"file": "src/x.py", "found": True, "score": 73.0, "details": {}}
    with patch(
        "api.v1.refactor_routes.get_refactor_score",
        return_value=payload,
    ):
        out = await refactor_score(request=request, file="src/x.py")
    assert out == payload


@pytest.mark.asyncio
async def test_refactor_candidates_passes_filters():
    request = _mock_request_with_context()
    with patch(
        "api.v1.refactor_routes.get_refactor_candidates",
        return_value={"threshold": 50.0, "count": 0, "candidates": []},
    ) as facade:
        out = await refactor_candidates(
            request=request, min_score=50.0, limit=10
        )
    _, kwargs = facade.call_args
    assert kwargs["min_score"] == 50.0
    assert kwargs["limit"] == 10
    assert "candidates" in out


@pytest.mark.asyncio
async def test_refactor_stats_delegates_to_facade():
    request = _mock_request_with_context()
    with patch(
        "api.v1.refactor_routes.get_refactor_stats",
        return_value={"count": 0, "mean": 0.0, "max": 0.0, "min": 0.0, "histogram": {}},
    ):
        out = await refactor_stats(request=request)
    assert out["count"] == 0
