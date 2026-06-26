# tests/api/v1/test_census_routes.py

"""Unit tests for census_routes — ADR-058 Phase 4, D1.

Mocks `will.governance.census_runner` so assertions target the route
translation layer. Covers ADR-058 verification criteria 2 (POST/GET
runs round-trip) and 3 (baseline create + diff, including missing
baseline → 422).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from api.v1.census_routes import (
    CreateBaselineRequest,
    CreateCensusRunRequest,
    census_diff,
    create_census_baseline,
    create_census_run,
    get_census_run,
    list_census_baselines,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


async def test_create_census_run_inserts_pending_and_schedules_background():
    """POST /census/runs inserts pending row, schedules drive_census, returns 202."""
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

    payload = CreateCensusRunRequest(snapshot=True, requested_by="api")

    out = await create_census_run(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/census/runs/{new_id}",
    }
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_get_census_run_returns_row():
    """GET /census/runs/{id} returns the persisted row as a dict."""
    run_id = uuid4()
    session = AsyncMock()
    row = {
        "id": run_id,
        "snapshot": True,
        "baseline_name": None,
        "status": "completed",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": {"metadata": {"version": "1.0.0"}},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_census_run(run_id=run_id, session=session)
    assert out["run_id"] == str(run_id)
    assert out["snapshot"] is True
    assert out["status"] == "completed"


async def test_get_census_run_returns_404_when_missing():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_census_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404


async def test_create_baseline_returns_payload():
    request = _mock_request_with_context()
    payload = CreateBaselineRequest(snapshot_file="repo_census_2026-05-18.json")
    with patch(
        "api.v1.census_routes.create_baseline",
        return_value={"name": "v2.0", "snapshot_file": "repo_census_2026-05-18.json"},
    ) as facade:
        out = await create_census_baseline(
            request=request, name="v2.0", payload=payload
        )
    facade.assert_called_once()
    assert out == {
        "baseline": {"name": "v2.0", "snapshot_file": "repo_census_2026-05-18.json"}
    }


async def test_create_baseline_returns_422_when_no_snapshot():
    """ValueError from the facade (no snapshot available) → 422."""
    request = _mock_request_with_context()
    payload = CreateBaselineRequest()
    with patch(
        "api.v1.census_routes.create_baseline",
        side_effect=ValueError("No census snapshot available"),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_census_baseline(request=request, name="v2.0", payload=payload)
    assert exc.value.status_code == 422
    assert "No census snapshot" in exc.value.detail


async def test_list_baselines_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.census_routes.list_baselines",
        return_value={"count": 2, "baselines": [{"name": "v1.0"}, {"name": "v2.0"}]},
    ):
        out = await list_census_baselines(request=request)
    assert out["count"] == 2


async def test_census_diff_passes_baseline_filter():
    request = _mock_request_with_context()
    with patch(
        "api.v1.census_routes.get_diff",
        return_value={"available": True, "baseline": "v2.0", "diff": {}},
    ) as facade:
        out = await census_diff(request=request, baseline="v2.0")
    _, kwargs = facade.call_args
    assert kwargs["baseline"] == "v2.0"
    assert out["available"] is True


async def test_census_diff_default_baseline_is_none():
    request = _mock_request_with_context()
    with patch(
        "api.v1.census_routes.get_diff",
        return_value={"available": False, "error": "Only one snapshot"},
    ) as facade:
        out = await census_diff(request=request, baseline=None)
    _, kwargs = facade.call_args
    assert kwargs["baseline"] is None
    assert out["available"] is False
