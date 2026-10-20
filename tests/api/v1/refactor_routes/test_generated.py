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


from unittest.mock import patch

import pytest

from api.v1.refactor_routes import refactor_stats


@pytest.mark.asyncio
# ID: 18418b32-8163-4f29-8aaa-1c4a6386d2c1
async def test_refactor_stats():
    expected_stats = {"high": 5, "medium": 10, "low": 3}

    mock_git_service = MagicMock()
    mock_git_service.repo_path = "/fake/repo/root"

    mock_core_context = MagicMock()
    mock_core_context.git_service = mock_git_service

    mock_app = MagicMock()
    mock_app.state.core_context = mock_core_context

    mock_request = MagicMock()
    mock_request.app = mock_app

    with patch(
        "api.v1.refactor_routes.get_refactor_stats",
        return_value=expected_stats,
    ) as mock_get_stats:
        result = await refactor_stats(mock_request)

    assert result == expected_stats
    mock_get_stats.assert_called_once_with("/fake/repo/root")


from api.v1.refactor_routes import refactor_candidates


# ID: 97896c96-cb0c-4504-8d94-f34f04096fc8
async def test_refactor_candidates():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    request.app.state.core_context.git_service.repo_path = "/fake/repo"

    expected = {"candidates": [{"file": "a.py", "score": 120}]}

    with patch(
        "api.v1.refactor_routes.get_refactor_candidates",
        return_value=expected,
    ) as mock_get:
        result = await refactor_candidates(request, min_score=50.0, limit=10)

    assert result == expected
    mock_get.assert_called_once_with("/fake/repo", min_score=50.0, limit=10)


import pytest

from api.v1.refactor_routes import refactor_score


@pytest.mark.asyncio
# ID: 5b177166-b7a0-4870-a8bb-3eb62b0ac600
async def test_refactor_score():
    request = MagicMock()
    request.app.state.core_context.git_service.repo_path = "/repo"

    expected_payload = {"found": True, "score": 0.87, "details": {"modules": 3}}

    with patch(
        "api.v1.refactor_routes.get_refactor_score",
        return_value=expected_payload,
    ) as mock_get:
        result = await refactor_score(request, file="src/foo.py")

    mock_get.assert_called_once_with("/repo", "src/foo.py")
    assert result == expected_payload


import pytest

from api.v1.refactor_routes import refactor_threshold


@pytest.mark.asyncio
# ID: 92bc8977-c719-44b3-b523-743274838639
async def test_refactor_threshold() -> None:
    request = MagicMock()
    core_context = MagicMock()
    repo_root = "/fake/repo/root"
    core_context.git_service.repo_path = repo_root
    request.app.state.core_context = core_context

    with patch(
        "api.v1.refactor_routes.get_refactor_threshold",
        return_value=0.75,
    ):
        result = await refactor_threshold(request)

    assert result == {"threshold": 0.75}
