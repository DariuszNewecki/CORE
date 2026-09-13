"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/api/v1/development_routes.py
- Symbol: start_development_cycle
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:42:56

ADR-160 D3 (2026-09-13): the five tests above this marker were auto-generated
against a `mock_payload = MagicMock()` that never set `.write` explicitly —
harmless when the route's status message didn't depend on it. It now does
(a write-capable request must not claim "running" while awaiting Governor
approval), and an unset `.write` on a MagicMock is truthy by default, which
would silently exercise the wrong branch. Each of those five tests now sets
`mock_payload.write = False` explicitly, restoring their original intent
(the unaffected dry-run/default path) rather than leaving it to a mock
default. The new tests below this marker cover the `write=True` path.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks, Request

from api.v1.development_routes import start_development_cycle


# Detected return type: The function returns a dict with keys 'task_id' and 'status'


async def test_start_development_cycle_creates_task_and_starts_background_job():
    """Test that start_development_cycle creates a task and adds background job."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Build a user authentication system"
    mock_payload.write = False

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
    ):
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


async def test_start_development_cycle_with_different_goal():
    """Test that different goals are properly passed to task creation."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Implement payment processing"
    mock_payload.write = False

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


async def test_start_development_cycle_returns_correct_structure():
    """Test that the function returns the expected dictionary structure."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Test goal"
    mock_payload.write = False

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


async def test_start_development_cycle_background_task_configuration():
    """Test that background task is properly configured with develop_from_goal."""
    # Mock dependencies
    mock_request = MagicMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.goal = "Background task test"
    mock_payload.write = False

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
    ):
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


# ------------------------------------------------- write=True (ADR-160 D3)


async def test_write_true_response_does_not_claim_work_is_running() -> None:
    """A write-capable request must not say "running" or "completed" --
    the write now creates a pending Proposal instead."""
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Fix the bug"
    mock_payload.write = True

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_session = AsyncMock()

    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    mock_task.id = uuid.uuid4()
    mock_task_repo.create.return_value = mock_task

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", AsyncMock()),
    ):
        result = await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )

    assert "running" not in result["status"]
    assert "completed" not in result["status"]
    assert "Proposal" in result["status"]
    assert "Governor" in result["status"]


async def test_write_true_relies_on_fail_closed_default_not_explicit_kwarg() -> None:
    """ADR-160 D3 polarity inversion: this route no longer wires
    create_proposal_only explicitly -- develop_from_goal's own fail-closed
    default (create_proposal_only = write and not legacy_direct_write)
    now produces the same behavior for write=True. Proof: the kwarg key is
    absent from the call, and develop_from_goal is called with write=True
    and no legacy_direct_write (see
    tests/will/autonomy/test_develop_from_goal_worker_shim.py for the
    default's own behavior)."""
    mock_request = MagicMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.goal = "Fix the bug"
    mock_payload.workflow_type = "code_modification"
    mock_payload.write = True

    captured_task_func = None

    def capture_task(func, *args, **kwargs):
        nonlocal captured_task_func
        captured_task_func = func

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_background_tasks.add_task.side_effect = capture_task

    mock_session = AsyncMock()
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    mock_task.id = uuid.uuid4()
    mock_task_repo.create.return_value = mock_task

    mock_develop_from_goal = AsyncMock()

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", mock_develop_from_goal),
    ):
        await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )
        assert captured_task_func is not None
        await captured_task_func()

    mock_develop_from_goal.assert_awaited_once()
    _, kwargs = mock_develop_from_goal.await_args
    assert kwargs["write"] is True
    assert "create_proposal_only" not in kwargs
    assert "legacy_direct_write" not in kwargs


async def test_write_false_does_not_pass_create_proposal_only() -> None:
    """Regression proof for the dry-run path on this same caller: unaffected.
    write=False produces create_proposal_only=False either way, and this
    route relies on the default rather than passing it explicitly."""
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_payload = MagicMock()
    mock_payload.goal = "Fix the bug"
    mock_payload.workflow_type = "code_modification"
    mock_payload.write = False

    captured_task_func = None

    def capture_task(func, *args, **kwargs):
        nonlocal captured_task_func
        captured_task_func = func

    mock_background_tasks = MagicMock(spec=BackgroundTasks)
    mock_background_tasks.add_task.side_effect = capture_task

    mock_session = AsyncMock()
    mock_task_repo = AsyncMock()
    mock_task = MagicMock()
    mock_task.id = uuid.uuid4()
    mock_task_repo.create.return_value = mock_task

    mock_develop_from_goal = AsyncMock()

    with (
        patch("api.v1.development_routes.TaskRepository", return_value=mock_task_repo),
        patch("api.v1.development_routes.develop_from_goal", mock_develop_from_goal),
    ):
        result = await start_development_cycle(
            request=mock_request,
            payload=mock_payload,
            background_tasks=mock_background_tasks,
            session=mock_session,
        )
        assert captured_task_func is not None
        await captured_task_func()

    mock_develop_from_goal.assert_awaited_once()
    _, kwargs = mock_develop_from_goal.await_args
    assert "create_proposal_only" not in kwargs
    assert result["status"] == "Task accepted and running."
