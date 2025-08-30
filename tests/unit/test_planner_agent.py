# tests/unit/test_planner_agent.py
import json
from unittest.mock import MagicMock

import pytest

from agents.models import ExecutionTask
from agents.plan_executor import PlanExecutionError
from agents.planner_agent import PlannerAgent

# --- MODIFICATION START ---
# We no longer need BaseLLMClient here, but we do need the CognitiveService
from core.cognitive_service import CognitiveService

# --- MODIFICATION END ---


@pytest.fixture
def mock_dependencies():
    """Mocks all external dependencies for the PlannerAgent."""

    # --- MODIFICATION START ---
    # Create a mock client that the service will return
    mock_client = MagicMock()

    # Create a mock CognitiveService
    mock_cognitive_service = MagicMock(spec=CognitiveService)
    # Configure the mock service to return our mock client when asked for a 'Planner'
    mock_cognitive_service.get_client_for_role.return_value = mock_client
    # --- MODIFICATION END ---

    return {
        # --- MODIFICATION START ---
        # The test now provides a cognitive_service, not an orchestrator_client
        "cognitive_service": mock_cognitive_service,
        # --- MODIFICATION END ---
        "prompt_pipeline": MagicMock(),
        "context": {"policies": {"agent_behavior_policy": {"planner_agent": {}}}},
    }


def test_create_execution_plan_success(mock_dependencies):
    """Tests that the planner can successfully parse a valid high-level plan."""
    agent = PlannerAgent(**mock_dependencies)
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
    # The make_request call is now on the client *returned by* the service
    mock_dependencies[
        "cognitive_service"
    ].get_client_for_role.return_value.make_request.return_value = (
        f"```json\n{plan_json}\n```"
    )

    plan = agent.create_execution_plan(goal)

    assert len(plan) == 1
    assert isinstance(plan[0], ExecutionTask)
    assert plan[0].action == "create_file"
    mock_dependencies["prompt_pipeline"].process.assert_called_once()


def test_create_execution_plan_fails_on_invalid_action(mock_dependencies):
    """Tests that the planner fails if the plan contains an invalid action."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Test goal"

    invalid_plan_json = json.dumps(
        [{"step": "Invalid action", "action": "make_coffee", "params": {}}]
    )
    # The make_request call is now on the client *returned by* the service
    mock_dependencies[
        "cognitive_service"
    ].get_client_for_role.return_value.make_request.return_value = (
        f"```json\n{invalid_plan_json}\n```"
    )

    with pytest.raises(PlanExecutionError):
        agent.create_execution_plan(goal)
