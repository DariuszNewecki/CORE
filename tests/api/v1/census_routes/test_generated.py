from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.v1.census_routes import census_diff


@pytest.mark.asyncio
# ID: 8e8d770f-8e88-4b56-8dc3-f6171cdff8a7
async def test_census_diff():
    mock_request = MagicMock()
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    expected_result = {"some": "diff"}
    with patch(
        "api.v1.census_routes.get_diff", return_value=expected_result
    ) as mock_get_diff:
        result = await census_diff(request=mock_request, baseline="some_baseline")
        mock_get_diff.assert_called_once_with(
            mock_core_context, baseline="some_baseline"
        )
        assert result == expected_result


import asyncio

from api.v1.census_routes import list_census_baselines


# ID: 58aa8ffb-06c3-4b31-93c7-7ebe809b19d9
def test_list_census_baselines():
    core_context = MagicMock()
    request = MagicMock()
    request.app.state.core_context = core_context

    expected = [{"id": "b2"}, {"id": "b1"}]

    with patch(
        "api.v1.census_routes.list_baselines", return_value=expected
    ) as mock_list:
        result = asyncio.run(list_census_baselines(request))

    mock_list.assert_called_once_with(core_context)
    assert result == expected


from api.v1.census_routes import create_census_baseline


# ID: 89ae4903-9cfe-4700-9742-ec12554a031e
async def test_create_census_baseline():
    request = MagicMock()
    request.app.state.core_context = MagicMock()

    payload = MagicMock()
    payload.snapshot_file = "snapshot.json"

    baseline = {"id": "b1", "name": "my-baseline"}

    with patch(
        "api.v1.census_routes.create_baseline", return_value=baseline
    ) as mock_create_baseline:
        result = await create_census_baseline(
            request=request, name="my-baseline", payload=payload
        )

    mock_create_baseline.assert_called_once_with(
        request.app.state.core_context,
        name="my-baseline",
        snapshot_file="snapshot.json",
    )
    assert result == {"baseline": baseline}


from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4


# ID: f1ce5753-570a-4b6f-9869-3839d0495c9d
def test_get_census_run():
    from api.v1.census_routes import get_census_run

    run_id = uuid4()
    requested_at = datetime(2024, 1, 1, 12, 0, 0)
    started_at = datetime(2024, 1, 1, 12, 0, 5)
    finished_at = datetime(2024, 1, 1, 12, 1, 0)

    row = {
        "id": run_id,
        "snapshot": "snap-1",
        "baseline_name": "baseline-a",
        "status": "completed",
        "requested_by": "tester",
        "requested_at": requested_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": {"ok": True},
        "error": None,
    }

    mappings = MagicMock()
    mappings.first.return_value = row
    result = MagicMock()
    result.mappings.return_value = mappings

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    out = asyncio.run(get_census_run(run_id, session=session))

    session.execute.assert_awaited_once()
    assert out == {
        "run_id": str(run_id),
        "snapshot": "snap-1",
        "baseline_name": "baseline-a",
        "status": "completed",
        "requested_by": "tester",
        "requested_at": requested_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "result": {"ok": True},
        "error": None,
    }


import uuid

import pytest

from api.v1.census_routes import create_census_run


@pytest.mark.asyncio
# ID: 9eb59730-7b6b-4905-86b4-3cf692a6c4f6
async def test_create_census_run():
    run_id = uuid.uuid4()

    request = MagicMock()
    request.app.state.core_context = MagicMock()

    response = MagicMock()
    background_tasks = MagicMock()

    payload = MagicMock()
    payload.snapshot = "snap-001"
    payload.requested_by = "tester"

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = run_id

    session = AsyncMock()
    session.execute.return_value = result_mock
    session.commit = AsyncMock()

    out = await create_census_run(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()

    background_tasks.add_task.assert_called_once()

    assert out == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/census/runs/{run_id}",
    }
