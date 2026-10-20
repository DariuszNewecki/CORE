from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from api.v1.coverage_routes import interactive_tests


@pytest.mark.asyncio
# ID: bc68649d-3378-4641-b1bb-91cadaceb691
async def test_interactive_tests():
    mock_request = MagicMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.target_file = "some/path.py"

    expected_result = {"status": "ok", "test_cases": ["test_a", "test_b"]}
    mock_run_tests = AsyncMock(return_value=expected_result)

    with patch("api.v1.coverage_routes.run_tests_interactive", mock_run_tests):
        result = await interactive_tests(request=mock_request, payload=mock_payload)

    assert result == expected_result
    mock_run_tests.assert_awaited_once_with(
        mock_core_context, target_file=mock_payload.target_file
    )


from datetime import UTC, datetime
from uuid import uuid4

from api.v1.coverage_routes import get_coverage_run


# ID: 7921520f-5cec-47ee-98e8-e785132c8992
async def test_get_coverage_run() -> None:
    run_id = uuid4()
    requested_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    started_at = datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC)
    finished_at = datetime(2024, 1, 1, 12, 2, 0, tzinfo=UTC)

    row = {
        "id": run_id,
        "target_file": "src/foo.py",
        "batch_priority": 3,
        "write": True,
        "status": "completed",
        "requested_by": "alice",
        "requested_at": requested_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": {"ok": True},
        "error": None,
    }

    mappings = MagicMock()
    mappings.first = MagicMock(return_value=row)
    result = MagicMock()
    result.mappings = MagicMock(return_value=mappings)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    response = await get_coverage_run(run_id=run_id, session=session)

    session.execute.assert_awaited_once()
    assert response == {
        "run_id": str(run_id),
        "target_file": "src/foo.py",
        "batch_priority": 3,
        "write": True,
        "status": "completed",
        "requested_by": "alice",
        "requested_at": requested_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "result": {"ok": True},
        "error": None,
    }


from uuid import UUID

import pytest

from api.v1.coverage_routes import generate_coverage_batch


@pytest.mark.asyncio
# ID: 70e99170-a2a4-4ac3-a960-9ff6a78ddf4d
async def test_generate_coverage_batch():
    from api.v1.coverage_routes import GenerateBatchRequest

    payload = GenerateBatchRequest(priority="high", write=True, requested_by="tester")

    request = MagicMock()
    request.app.state.core_context = MagicMock()

    response = MagicMock()
    background_tasks = MagicMock()

    run_id = UUID("0d4e6f2a-3b5c-4d7e-8f9a-0b1c2d3e4f5c")
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = run_id

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    result = await generate_coverage_batch(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert result == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/coverage/runs/{run_id}",
    }
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    background_tasks.add_task.assert_called_once()


import pytest
from fastapi import BackgroundTasks, Response

from api.v1.coverage_routes import generate_coverage


@pytest.mark.asyncio
# ID: 96238e4b-be43-44f1-a315-786a0c2c676e
async def test_generate_coverage():
    run_id = uuid4()

    payload = MagicMock()
    payload.write = True
    payload.target_file = "src/foo.py"
    payload.requested_by = "tester"

    request = MagicMock(spec=Request)
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.core_context = MagicMock()

    response = MagicMock(spec=Response)

    background_tasks = MagicMock(spec=BackgroundTasks)

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    exec_result = MagicMock()
    exec_result.scalar_one = MagicMock(return_value=run_id)
    session.execute.return_value = exec_result

    result = await generate_coverage(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert result == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/coverage/runs/{run_id}",
    }
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    background_tasks.add_task.assert_called_once()
