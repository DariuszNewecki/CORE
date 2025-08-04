# tests/unit/test_planner_agent.py
import json
import pytest
from agents.planner_agent import PlannerAgent
from unittest.mock import MagicMock #, AsyncMock, patch


@pytest.fixture
def mock_dependencies(mocker):
    """Mocks all external dependencies for the PlannerAgent."""
    mock_orchestrator = MagicMock()
    mock_generator = MagicMock()
    mock_file_handler = MagicMock()
    mock_git_service = MagicMock()
    mock_intent_guard = MagicMock()
    
    # Configure the mock file_handler to have a 'repo_path' attribute
    mock_file_handler.repo_path = "/fake/repo"

    mocker.patch('core.prompt_pipeline.PromptPipeline', return_value=MagicMock())

    return {
        "orchestrator_client": mock_orchestrator,
        "generator_client": mock_generator,
        "file_handler": mock_file_handler,
        "git_service": mock_git_service,
        "intent_guard": mock_intent_guard,
    }

def test_create_execution_plan_success(mock_dependencies):
    """Tests that the planner can successfully create a plan from a goal."""
    # Arrange
    agent = PlannerAgent(**mock_dependencies)
    goal = "This is a test goal."
    
    # Mock the orchestrator's response
    plan_json = json.dumps([{"step": "Test Step", "prompt": "Do a thing", "expects_writes": True}])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{plan_json}\n```"

    # Act
    plan = agent.create_execution_plan(goal)

    # Assert
    mock_dependencies["orchestrator_client"].make_request.assert_called_once()
    assert isinstance(plan, list)
    assert len(plan) == 1
    assert plan[0]["step"] == "Test Step"

def test_create_execution_plan_failure_on_bad_json(mock_dependencies):
    """Tests that the planner returns an empty list if the LLM gives bad JSON."""
    # Arrange
    agent = PlannerAgent(**mock_dependencies)
    goal = "This is a test goal."
    mock_dependencies["orchestrator_client"].make_request.return_value = "This is not JSON."

    # Act
    plan = agent.create_execution_plan(goal)

    # Assert
    assert plan == []

@pytest.mark.asyncio
async def test_execute_plan_success(mock_dependencies):
    """Tests a successful execution of a simple, single-step plan."""
    # Arrange
    agent = PlannerAgent(**mock_dependencies)
    plan = [{"step": "Create test file", "prompt": "[[write:src/test.py]]", "expects_writes": True}]

    # Mock downstream service calls
    mock_dependencies["generator_client"].make_request.return_value = "[[write:src/test.py]]\nprint('hello')\n[[/write]]"
    mock_dependencies["file_handler"].add_pending_write.return_value = "mock_pending_id"
    mock_dependencies["file_handler"].confirm_write.return_value = {"status": "success", "file_path": "src/test.py"}
    mock_dependencies["git_service"].is_git_repo.return_value = True

    # Act
    success, message = await agent.execute_plan(plan)

    # Assert
    assert success is True
    assert message == "✅ Plan executed successfully."
    mock_dependencies["generator_client"].make_request.assert_called_once()
    mock_dependencies["file_handler"].confirm_write.assert_called_once_with("mock_pending_id")
    mock_dependencies["git_service"].add.assert_called_once_with("src/test.py")
    mock_dependencies["git_service"].commit.assert_called_once()
