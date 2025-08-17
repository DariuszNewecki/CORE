# tests/unit/test_planner_agent.py
import json
from unittest.mock import MagicMock

import pytest

from agents.models import ExecutionTask
from agents.plan_executor import PlanExecutionError
from agents.planner_agent import PlannerAgent, PlannerConfig


@pytest.fixture
def mock_dependencies():
    """Mocks all external dependencies for the NEW, simpler PlannerAgent."""
    return {
        "orchestrator_client": MagicMock(),
        "prompt_pipeline": MagicMock(),
        "config": PlannerConfig(),
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
    mock_dependencies["orchestrator_client"].make_request.return_value = (
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
    mock_dependencies["orchestrator_client"].make_request.return_value = (
        f"```json\n{invalid_plan_json}\n```"
    )

    with pytest.raises(PlanExecutionError):
        agent.create_execution_plan(goal)
