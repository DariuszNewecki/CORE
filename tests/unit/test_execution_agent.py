# tests/unit/test_execution_agent.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.execution_agent import ExecutionAgent
from shared.models import ExecutionTask, PlanExecutionError, TaskParams

# This is our valid, constitutionally-compliant plan
VALID_PLAN = [
    ExecutionTask(
        step="Create a safe file.",
        action="autonomy.self_healing.format_code",  # This is in allowed_actions
        params=TaskParams(file_path="src/safe_dir/test.py"),  # This is in allowed_paths
    )
]

# This plan contains an action not permitted by the policy
INVALID_ACTION_PLAN = [
    ExecutionTask(
        step="Do something dangerous.",
        action="system.dangerous.execute_shell",  # NOT in allowed_actions
        params=TaskParams(file_path="src/safe_dir/test.py"),
    )
]

# This plan targets a constitutionally forbidden file path
INVALID_PATH_PLAN = [
    ExecutionTask(
        step="Modify the constitution.",
        action="autonomy.self_healing.format_code",  # Action is ok...
        params=TaskParams(
            file_path=".intent/charter/policies/safety_policy.yaml"
        ),  # ...but path is forbidden
    )
]


@pytest.fixture
def mock_execution_agent(tmp_path):
    """A pytest fixture to create a fully mocked ExecutionAgent for testing."""
    # 1. Create a mock constitution on the fly
    intent_dir = tmp_path / ".intent"
    (intent_dir / "charter" / "policies").mkdir(parents=True)

    # The agent_policy.yaml is needed for max_correction_attempts
    (intent_dir / "charter" / "policies" / "agent_policy.yaml").write_text(
        "execution_agent:\n  max_correction_attempts: 1"
    )

    # The micro_proposal_policy.yaml is the law we are testing against
    micro_policy = """
    rules:
      - id: safe_actions
        allowed_actions:
          - "autonomy.self_healing.format_code"
      - id: safe_paths
        allowed_paths:
          - "src/safe_dir/**"
        forbidden_paths:
          - ".intent/**"
    """
    (intent_dir / "charter" / "policies" / "micro_proposal_policy.yaml").write_text(
        micro_policy
    )

    # 2. Create mock dependencies for the ExecutionAgent
    mock_cognitive_service = MagicMock()
    mock_prompt_pipeline = MagicMock()
    mock_plan_executor = MagicMock()
    mock_auditor_context = MagicMock()

    # The agent needs a GitService to get the repo_path
    mock_git_service = MagicMock()
    mock_git_service.repo_path = tmp_path
    mock_plan_executor.git_service = mock_git_service

    # 3. Instantiate the real ExecutionAgent with mocked dependencies
    agent = ExecutionAgent(
        cognitive_service=mock_cognitive_service,
        prompt_pipeline=mock_prompt_pipeline,
        plan_executor=mock_plan_executor,
        auditor_context=mock_auditor_context,
    )
    return agent


def test_verify_plan_accepts_valid_plan(mock_execution_agent):
    """
    GIVEN a constitutionally valid plan
    WHEN the agent verifies the plan
    THEN it should complete without raising an exception.
    """
    # Act & Assert
    # The test passes if no exception is raised
    mock_execution_agent._verify_plan(VALID_PLAN)


def test_verify_plan_rejects_invalid_action(mock_execution_agent):
    """
    GIVEN a plan with an action not in the policy's allowed_actions list
    WHEN the agent verifies the plan
    THEN it should raise a PlanExecutionError.
    """
    # Act & Assert
    with pytest.raises(
        PlanExecutionError,
        match="Action 'system.dangerous.execute_shell' is not in the list of allowed safe actions",
    ):
        mock_execution_agent._verify_plan(INVALID_ACTION_PLAN)


def test_verify_plan_rejects_forbidden_path(mock_execution_agent):
    """
    GIVEN a plan targeting a path in the policy's forbidden_paths list
    WHEN the agent verifies the plan
    THEN it should raise a PlanExecutionError.
    """
    # Act & Assert
    with pytest.raises(
        PlanExecutionError, match="is explicitly forbidden by the micro-proposal policy"
    ):
        mock_execution_agent._verify_plan(INVALID_PATH_PLAN)


@pytest.mark.asyncio
async def test_execute_plan_aborts_on_invalid_plan(mock_execution_agent):
    """
    GIVEN an invalid plan
    WHEN the main execute_plan method is called
    THEN it should fail fast on the verification step and not attempt execution.
    """
    # Arrange
    # We can spy on the _generate_and_validate_all_tasks method to ensure it's never called.
    mock_execution_agent._generate_and_validate_all_tasks = AsyncMock()

    # Act
    success, message = await mock_execution_agent.execute_plan(
        "A test goal", INVALID_ACTION_PLAN
    )

    # Assert
    assert not success
    assert "Action 'system.dangerous.execute_shell' is not in the list" in message
    # Crucially, assert that the agent never even tried to start the execution loop
    mock_execution_agent._generate_and_validate_all_tasks.assert_not_called()
