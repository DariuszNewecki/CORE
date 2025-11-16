# tests/unit/test_execution_agent.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.models import ExecutionTask, PlanExecutionError, TaskParams
from will.agents.execution_agent import ExecutionAgent


@pytest.fixture
def mock_execution_agent(mock_core_env):
    """Uses the canonical mock environment to create a valid ExecutionAgent."""
    # --- THIS IS THE FIX ---
    # The constructor expects coder_agent, plan_executor, and auditor_context.
    mock_coder_agent = MagicMock()
    mock_plan_executor = MagicMock()
    mock_plan_executor.execute_plan = AsyncMock()
    mock_auditor_context = MagicMock()

    agent = ExecutionAgent(
        coder_agent=mock_coder_agent,
        plan_executor=mock_plan_executor,
        auditor_context=mock_auditor_context,
    )
    return agent, mock_plan_executor
    # --- END OF FIX ---


@pytest.mark.anyio
async def test_execute_plan_success(mock_execution_agent):
    """Tests that a valid plan is passed to the plan executor."""
    agent, mock_executor = mock_execution_agent
    valid_plan = [
        ExecutionTask(
            step="Read a file",
            action="read_file",
            params=TaskParams(file_path="src/main.py"),
        )
    ]

    success, message = await agent.execute_plan("A test goal", valid_plan)

    assert success
    assert message == "✅ Plan executed successfully."
    mock_executor.execute_plan.assert_awaited_once_with(valid_plan)


@pytest.mark.anyio
async def test_execute_plan_handles_executor_failure(mock_execution_agent):
    """Tests that the agent correctly reports a failure from the plan executor."""
    agent, mock_executor = mock_execution_agent
    mock_executor.execute_plan.side_effect = PlanExecutionError("Something went wrong")

    plan = [
        ExecutionTask(
            step="Read a file",
            action="read_file",
            params=TaskParams(file_path="src/main.py"),
        )
    ]

    success, message = await agent.execute_plan("A test goal", plan)

    assert not success
    assert "Plan execution failed during orchestration: Something went wrong" in message
