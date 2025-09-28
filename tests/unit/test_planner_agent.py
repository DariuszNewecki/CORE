# tests/unit/test_planner_agent.py
import json
from unittest.mock import MagicMock

import pytest

from core.agents.planner_agent import PlannerAgent
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.models import ExecutionTask, PlanExecutionError


@pytest.fixture
def mock_cognitive_service():
    mock_client = MagicMock()
    mock_service = MagicMock(spec=CognitiveService)
    mock_service.get_client_for_role.return_value = mock_client
    return mock_service


# REMOVED the old setup_test_environment function


def test_create_execution_plan_success(
    mock_cognitive_service, mock_fs_with_constitution, mocker
):
    """Tests that the planner can successfully parse a valid high-level plan."""
    mocker.patch.object(settings, "MIND", mock_fs_with_constitution / ".intent")

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
    mock_cognitive_service.get_client_for_role.return_value.make_request.return_value = (
        f"```json\n{plan_json}\n```"
    )

    plan = agent.create_execution_plan(goal)

    assert len(plan) == 1
    assert isinstance(plan[0], ExecutionTask)
    assert plan[0].action == "create_file"


def test_create_execution_plan_fails_on_invalid_action(
    mock_cognitive_service, mock_fs_with_constitution, mocker
):
    """Tests that the planner fails if the plan contains an invalid action."""
    mocker.patch.object(settings, "MIND", mock_fs_with_constitution / ".intent")

    agent = PlannerAgent(cognitive_service=mock_cognitive_service)
    goal = "Test goal"

    invalid_plan_json = json.dumps(
        [{"step": "Invalid action", "action": "make_coffee", "params": {}}]
    )
    mock_cognitive_service.get_client_for_role.return_value.make_request.return_value = (
        f"```json\n{invalid_plan_json}\n```"
    )

    with pytest.raises(PlanExecutionError):
        agent.create_execution_plan(goal)
