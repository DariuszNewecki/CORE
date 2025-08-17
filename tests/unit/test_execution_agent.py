# tests/unit/test_execution_agent.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.execution_agent import ExecutionAgent
from agents.models import ExecutionTask, TaskParams
from agents.plan_executor import PlanExecutionError


@pytest.fixture
def mock_dependencies():
    """Mocks all external dependencies for the ExecutionAgent."""
    # Use AsyncMock for any objects that have async methods to be called
    return {
        "generator_client": MagicMock(),
        "prompt_pipeline": MagicMock(),
        "plan_executor": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_execute_plan_success(mock_dependencies):
    """Tests that a valid plan is executed correctly."""
    agent = ExecutionAgent(**mock_dependencies)
    goal = "Test goal"
    plan = [
        ExecutionTask(
            step="Create a file",
            action="create_file",
            params=TaskParams(file_path="test.py"),
        )
    ]

    agent.generator.make_request.return_value = "print('Hello')"
    mock_dependencies["prompt_pipeline"].process.return_value = "enriched_prompt"
    mock_dependencies["plan_executor"].execute_plan.return_value = (True, "Success")

    # Mock the git_service used by the context manager
    agent.executor.git_service = MagicMock()
    agent.executor.git_service.is_git_repo.return_value = False # Disable git logic for this test

    success, message = await agent.execute_plan(goal, plan)

    assert success is True
    assert message == "✅ Plan executed successfully."
    agent.generator.make_request.assert_called_once()
    mock_dependencies["plan_executor"].execute_plan.assert_awaited_once()
    executed_plan = mock_dependencies["plan_executor"].execute_plan.call_args[0][0]
    assert executed_plan[0].params.code == "print('Hello')"


@pytest.mark.asyncio
async def test_execute_plan_fails_on_code_generation_failure(mock_dependencies):
    """Tests that the process fails if code generation returns nothing."""
    agent = ExecutionAgent(**mock_dependencies)
    goal = "Test goal"
    plan = [
        ExecutionTask(
            step="Create a file",
            action="create_file",
            params=TaskParams(file_path="test.py"),
        )
    ]

    agent.generator.make_request.return_value = ""

    success, message = await agent.execute_plan(goal, plan)

    assert success is False
    assert "Code generation failed" in message
    mock_dependencies["plan_executor"].execute_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_plan_handles_executor_failure(mock_dependencies):
    """Tests that failures from the PlanExecutor are propagated correctly."""
    agent = ExecutionAgent(**mock_dependencies)
    goal = "Test goal"
    plan = [
        ExecutionTask(
            step="Create a file",
            action="create_file",
            params=TaskParams(file_path="test.py"),
        )
    ]

    agent.generator.make_request.return_value = "print('Hello')"
    mock_dependencies["plan_executor"].execute_plan.side_effect = PlanExecutionError(
        "Validation failed", violations=[{"rule": "E999"}]
    )
    
    # Mock the git_service used by the context manager
    agent.executor.git_service = MagicMock()
    agent.executor.git_service.is_git_repo.return_value = True
    agent.executor.git_service.get_current_commit.return_value = "dummy_hash"


    success, message = await agent.execute_plan(goal, plan)

    assert success is False
    assert "Plan execution failed: Validation failed" in message
