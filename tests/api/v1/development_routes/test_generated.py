from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.development_routes import start_development_cycle


@pytest.mark.asyncio
# ID: 4d3d28e9-52f8-43df-94c0-92b6293ebad8
async def test_start_development_cycle():
    # Arrange
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    payload = MagicMock()
    payload.goal = "Build a feature"
    payload.workflow_type = "autonomous"
    payload.write = True

    background_tasks = MagicMock(spec=BackgroundTasks)

    mock_session = AsyncMock(spec=AsyncSession)

    mock_task_repo = MagicMock()
    mock_new_task = MagicMock()
    mock_new_task.id = "test-task-uuid"
    mock_task_repo.create = AsyncMock(return_value=mock_new_task)

    with patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo):
        # Act
        result = await start_development_cycle(
            request=mock_request,
            payload=payload,
            background_tasks=background_tasks,
            session=mock_session,
        )

    # Assert
    mock_task_repo.create.assert_awaited_once_with(
        intent=payload.goal, assigned_role="AutonomousDeveloper", status="planning"
    )

    assert result == {
        "task_id": "test-task-uuid",
        "status": "Task accepted and running.",
    }

    # Verify that background_tasks.add_task was called with the run_development closure
    background_tasks.add_task.assert_called_once()
    args, _ = background_tasks.add_task.call_args
    run_func = args[0]
    assert callable(run_func)
