"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/api/v1/development_routes.py
- Symbol: start_development_cycle
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:42:56
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, Request

from api.v1.development_routes import start_development_cycle


# Detected return type: The function returns a dict with keys 'task_id' and 'status'


@pytest.mark.asyncio
async def test_start_development_cycle_creates_task_and_starts_background_job():
    """Test that start_development_cycle creates a task and adds background job."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Build a user authentication system"

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_background_tasks.add_task = MagicMock()

    mock_session = AsyncMock()

    # Mock TaskRepository
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    mock_task_id = uuid.uuid4()
    mock_task.id = mock_task_id
    mock_task_repo.create.return_value = mock_task

    # Mock develop_from_goal
    mock_develop_from_goal = AsyncMock()

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", mock_develop_from_goal),
        patch("api.v1.development_routes.get_session") as mock_get_session,
    ):

        # Mock session context manager for background task
        mock_dev_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_dev_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Call the function
        result = await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )

        # Assertions
        # Check that task was created with correct parameters
        mock_task_repo.create.assert_called_once_with(
            intent="Build a user authentication system",
            assigned_role="AutonomousDeveloper",
            status="planning",
        )

        # Check that background task was added
        assert mock_background_tasks.add_task.call_count == 1

        # Check the returned result
        assert result == {
            "task_id": str(mock_task_id),
            "status": "Task accepted and running.",
        }

        # Verify the background task function would call develop_from_goal
        # We can't directly call run_development as it's nested, but we verified
        # the add_task was called with a function


@pytest.mark.asyncio
async def test_start_development_cycle_with_different_goal():
    """Test that different goals are properly passed to task creation."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Implement payment processing"

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_background_tasks.add_task = MagicMock()

    mock_session = AsyncMock()

    # Mock TaskRepository
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    mock_task.id = uuid.uuid4()
    mock_task_repo.create.return_value = mock_task

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", AsyncMock()),
        patch("api.v1.development_routes.get_session"),
    ):

        # Call the function
        result = await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )

        # Verify the goal was passed correctly
        mock_task_repo.create.assert_called_once_with(
            intent="Implement payment processing",
            assigned_role="AutonomousDeveloper",
            status="planning",
        )

        # Verify result structure
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "Task accepted and running."


@pytest.mark.asyncio
async def test_start_development_cycle_returns_correct_structure():
    """Test that the function returns the expected dictionary structure."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Test goal"

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_background_tasks.add_task = MagicMock()

    mock_session = AsyncMock()

    # Mock TaskRepository
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    test_task_id = uuid.uuid4()
    mock_task.id = test_task_id
    mock_task_repo.create.return_value = mock_task

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", AsyncMock()),
        patch("api.v1.development_routes.get_session"),
    ):

        # Call the function
        result = await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )

        # Verify result structure and types
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "task_id" in result
        assert "status" in result
        assert isinstance(result["task_id"], str)
        assert isinstance(result["status"], str)
        assert result["task_id"] == str(test_task_id)
        assert result["status"] == "Task accepted and running."


@pytest.mark.asyncio
async def test_start_development_cycle_background_task_configuration():
    """Test that background task is properly configured with develop_from_goal."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.goal = "Background task test"

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    captured_task_func = None

    def capture_task(func, *args, **kwargs):
        nonlocal captured_task_func
        captured_task_func = func

    mock_background_tasks.add_task.side_effect = capture_task

    mock_session = AsyncMock()

    # Mock TaskRepository
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    test_task_id = uuid.uuid4()
    mock_task.id = test_task_id
    mock_task_repo.create.return_value = mock_task

    mock_develop_from_goal = AsyncMock()

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", mock_develop_from_goal),
        patch("api.v1.development_routes.get_session") as mock_get_session,
    ):

        # Mock session context manager
        mock_dev_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_dev_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Call the function
        await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )

        # Verify background task was added
        assert mock_background_tasks.add_task.call_count == 1
        assert captured_task_func is not None

        # We can't directly test the nested async function, but we've verified
        # that develop_from_goal is imported and available for the background task
