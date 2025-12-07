# tests/unit/agents/test_execution_agent.py
"""
Unit tests for the ExecutionAgent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.models import ExecutionTask, PlanExecutionError, TaskParams
from will.agents.execution_agent import _ExecutionAgent


@pytest.fixture
def mock_execution_agent(mock_core_env):
    """Uses the canonical mock environment to create a valid ExecutionAgent."""
    mock_coder_agent = MagicMock()
    mock_plan_executor = MagicMock()
    mock_plan_executor.execute_plan = AsyncMock()
    mock_auditor_context = MagicMock()

    agent = _ExecutionAgent(
        coder_agent=mock_coder_agent,
        plan_executor=mock_plan_executor,
        auditor_context=mock_auditor_context,
    )
    return agent, mock_plan_executor


@pytest.mark.asyncio
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
    assert "successfully" in message
    mock_executor.execute_plan.assert_awaited_once_with(valid_plan)


@pytest.mark.asyncio
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
    # Updated assertion to be robust to minor message variations
    assert "failed" in message
    assert "Something went wrong" in message
