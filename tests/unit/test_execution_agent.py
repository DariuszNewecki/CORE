# tests/unit/test_execution_agent.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.execution_agent import ExecutionAgent
from shared.models import ExecutionTask, PlanExecutionError, TaskParams

VALID_PLAN = [
    ExecutionTask(
        step="...",
        action="autonomy.self_healing.format_code",
        params=TaskParams(file_path="src/safe_dir/test.py"),
    )
]
INVALID_ACTION_PLAN = [
    ExecutionTask(
        step="...",
        action="system.dangerous.execute_shell",
        params=TaskParams(file_path="src/safe_dir/test.py"),
    )
]
INVALID_PATH_PLAN = [
    ExecutionTask(
        step="...",
        action="autonomy.self_healing.format_code",
        params=TaskParams(file_path=".intent/charter/policies/safety_policy.yaml"),
    )
]


@pytest.fixture
def mock_execution_agent(mock_core_env):
    """Uses the canonical mock environment to create a valid ExecutionAgent."""
    mock_cognitive_service = MagicMock()
    mock_prompt_pipeline = MagicMock()
    mock_auditor_context = MagicMock()
    mock_git_service = MagicMock(repo_path=mock_core_env)
    mock_plan_executor = MagicMock(git_service=mock_git_service)
    mock_plan_executor.execute_plan = AsyncMock()

    # The agent will now correctly load its policies from the mock environment
    agent = ExecutionAgent(
        cognitive_service=mock_cognitive_service,
        prompt_pipeline=mock_prompt_pipeline,
        plan_executor=mock_plan_executor,
        auditor_context=mock_auditor_context,
    )
    return agent


def test_verify_plan_accepts_valid_plan(mock_execution_agent):
    mock_execution_agent._verify_plan(VALID_PLAN)


def test_verify_plan_rejects_invalid_action(mock_execution_agent):
    with pytest.raises(
        PlanExecutionError, match="not in the list of allowed safe actions"
    ):
        mock_execution_agent._verify_plan(INVALID_ACTION_PLAN)


def test_verify_plan_rejects_forbidden_path(mock_execution_agent):
    with pytest.raises(PlanExecutionError, match="is explicitly forbidden"):
        mock_execution_agent._verify_plan(INVALID_PATH_PLAN)


@pytest.mark.asyncio
async def test_execute_plan_aborts_on_invalid_plan(mock_execution_agent):
    mock_execution_agent._generate_and_validate_all_tasks = AsyncMock()
    success, message = await mock_execution_agent.execute_plan(
        "A test goal", INVALID_ACTION_PLAN
    )
    assert not success
    assert "Action 'system.dangerous.execute_shell' is not in the list" in message
    mock_execution_agent._generate_and_validate_all_tasks.assert_not_called()
