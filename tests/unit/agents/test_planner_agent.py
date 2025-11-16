# tests/unit/test_planner_agent.py
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.models import ExecutionTask, PlanExecutionError
from will.agents.planner_agent import PlannerAgent
from will.orchestration.cognitive_service import CognitiveService


@pytest.fixture
def mock_cognitive_service():
    """Mocks the CognitiveService and its client for async methods."""
    mock_client = MagicMock()
    mock_client.make_request_async = AsyncMock()

    mock_service = MagicMock(spec=CognitiveService)
    mock_service.aget_client_for_role = AsyncMock(return_value=mock_client)

    return mock_service


@pytest.mark.anyio
async def test_create_execution_plan_success(mock_cognitive_service, mock_core_env):
    """Tests that the planner can successfully parse a valid high-level plan."""
    agent = PlannerAgent(cognitive_service=mock_cognitive_service)
    goal = "Test goal"

    plan_json = json.dumps(
        [
            {
                "step": "A valid step",
                "action": "create_file",
                "params": {"file_path": "src/test.py"},
            }
        ]
    )
    mock_client = await mock_cognitive_service.aget_client_for_role("Planner")
    mock_client.make_request_async.return_value = f"```json\n{plan_json}\n```"

    plan = await agent.create_execution_plan(goal)

    assert len(plan) == 1
    assert isinstance(plan[0], ExecutionTask)
    assert plan[0].action == "create_file"


@pytest.mark.anyio
async def test_create_execution_plan_raises_plan_error_on_bad_data(
    mock_cognitive_service, mock_core_env
):
    """
    Tests that the planner raises a PlanExecutionError after failing to
    parse a structurally invalid response from the LLM after all retries.
    """
    agent = PlannerAgent(cognitive_service=mock_cognitive_service)
    goal = "Test goal"

    invalid_plan_json = json.dumps(
        [{"step": "Invalid structure", "action": "create_file"}]
    )

    mock_client = await mock_cognitive_service.aget_client_for_role("Planner")
    mock_client.make_request_async.return_value = f"```json\n{invalid_plan_json}\n```"

    with pytest.raises(
        PlanExecutionError, match="Failed to create a valid plan after max retries"
    ):
        await agent.create_execution_plan(goal)
