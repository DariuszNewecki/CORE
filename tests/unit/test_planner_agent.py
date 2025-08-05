# tests/unit/test_planner_agent.py
import json
import pytest
from agents.planner_agent import PlannerAgent
from unittest.mock import MagicMock, patch
from pathlib import Path # <-- ADD THIS IMPORT

@pytest.fixture
def mock_dependencies(mocker):
    """Mocks all external dependencies for the PlannerAgent."""
    mock_file_handler = MagicMock()
    # --- THIS IS THE FIX ---
    # Provide the repo_path as a Path object, not a string.
    mock_file_handler.repo_path = Path("/fake/repo")
    
    return {
        "orchestrator_client": MagicMock(),
        "generator_client": MagicMock(),
        "file_handler": mock_file_handler,
        "git_service": MagicMock(),
        "intent_guard": MagicMock(),
    }

def test_create_execution_plan_success(mock_dependencies):
    """Tests that the planner can successfully create a plan from a goal."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "This is a test goal."
    plan_json = json.dumps([{"step": "Test Step", "action": "test_action", "params": {}}])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{plan_json}\n```"
    
    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        plan = agent.create_execution_plan(goal)

    mock_dependencies["orchestrator_client"].make_request.assert_called_once()
    assert isinstance(plan, list)
    assert len(plan) == 1
    assert plan[0]["step"] == "Test Step"

def test_create_execution_plan_failure_on_bad_json(mock_dependencies):
    """Tests that the planner returns an empty list if the LLM gives bad JSON."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "This is a test goal."
    mock_dependencies["orchestrator_client"].make_request.return_value = "This is not JSON."
    
    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        plan = agent.create_execution_plan(goal)

    assert plan == []

@pytest.mark.asyncio
async def test_execute_plan_success_for_add_tag(mock_dependencies, mocker):
    """Tests a successful execution of the surgical 'add_capability_tag' action."""
    # Arrange
    agent = PlannerAgent(**mock_dependencies)
    
    plan = [{
        "step": "Tag the '_run_command' function",
        "action": "add_capability_tag",
        "params": {
            "file_path": "src/core/git_service.py",
            "symbol_name": "_run_command",
            "tag": "change_safety_enforcement"
        }
    }]

    mock_dependencies["file_handler"].add_pending_write.return_value = "mock_pending_id"
    mock_dependencies["file_handler"].confirm_write.return_value = {"status": "success"}
    mock_dependencies["git_service"].is_git_repo.return_value = True

    mock_file_content = "def _run_command(self, command: list) -> str:\n    pass"
    mocker.patch("pathlib.Path.read_text", return_value=mock_file_content)
    mocker.patch("pathlib.Path.exists", return_value=True)

    mocker.patch(
        "agents.planner_agent.validate_code", 
        return_value={"status": "clean", "code": "validated_code"}
    )
    
    # Act
    success, message = await agent.execute_plan(plan)

    # Assert
    assert success is True
    assert message == "✅ Plan executed successfully."
    mock_dependencies["file_handler"].add_pending_write.assert_called_once()
    mock_dependencies["file_handler"].confirm_write.assert_called_once_with("mock_pending_id")
    mock_dependencies["git_service"].add.assert_called_once_with("src/core/git_service.py")
    mock_dependencies["git_service"].commit.assert_called_once()
    mock_dependencies["generator_client"].make_request.assert_not_called()