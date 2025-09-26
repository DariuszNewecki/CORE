# tests/unit/test_planner_agent.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.agents.planner_agent import PlannerAgent
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.models import ExecutionTask, PlanExecutionError


@pytest.fixture
def mock_cognitive_service():
    """Provides a mocked CognitiveService that returns a mock client."""
    mock_client = MagicMock()
    mock_service = MagicMock(spec=CognitiveService)
    mock_service.get_client_for_role.return_value = mock_client
    return mock_service


def setup_test_environment(tmp_path: Path):
    """Helper to create necessary constitutional files in a temp directory."""
    intent_dir = tmp_path / ".intent"
    # --- FIX: Create the correct directory structure ---
    (intent_dir / "mind" / "prompts").mkdir(parents=True)
    (intent_dir / "mind" / "config").mkdir(parents=True)

    prompt_file = intent_dir / "mind" / "prompts" / "planner_agent.prompt"
    prompt_file.write_text("Goal: {goal}\nActions:\n{action_descriptions}")

    actions_file = intent_dir / "mind" / "config" / "actions.yaml"
    actions_file.write_text(
        "actions:\n  - name: create_file\n    description: Creates a file.\n    required_parameters: ['file_path']"
    )
    return intent_dir


def test_create_execution_plan_success(mock_cognitive_service, tmp_path, mocker):
    """Tests that the planner can successfully parse a valid high-level plan."""
    intent_dir = setup_test_environment(tmp_path)
    mocker.patch.object(settings, "MIND", intent_dir)

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
    mock_cognitive_service, tmp_path, mocker
):
    """Tests that the planner fails if the plan contains an invalid action."""
    intent_dir = setup_test_environment(tmp_path)
    mocker.patch.object(settings, "MIND", intent_dir)

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
