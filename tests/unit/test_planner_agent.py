# tests/unit/test_planner_agent.py
import json
import pytest
from agents.planner_agent import PlannerAgent, ExecutionTask, PlannerConfig
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from pydantic import ValidationError

@pytest.fixture
def mock_dependencies():
    """Mocks all external dependencies for the PlannerAgent."""
    return {
        "orchestrator_client": MagicMock(),
        "generator_client": MagicMock(),
        "file_handler": MagicMock(repo_path=Path("/fake/repo")),
        "git_service": MagicMock(),
        "intent_guard": MagicMock(),
        "config": PlannerConfig(auto_commit=False) # Disable auto-commit for most tests
    }

def test_create_execution_plan_success(mock_dependencies):
    """Tests that the planner can successfully parse and validate a correct plan."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Test goal"
    
    # A valid plan that matches the Pydantic models
    plan_json = json.dumps([{
        "step": "Tag a function",
        "action": "add_capability_tag",
        "params": {
            "file_path": "src/test.py",
            "symbol_name": "test_func",
            "tag": "test_capability"
        }
    }])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{plan_json}\n```"

    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        plan = agent.create_execution_plan(goal)

    assert len(plan) == 1
    assert isinstance(plan[0], ExecutionTask)
    assert plan[0].params.tag == "test_capability"

def test_create_execution_plan_fails_on_validation_error(mock_dependencies):
    """Tests that the planner returns an empty list if the plan violates the Pydantic schema."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Test goal"
    
    # An invalid plan with a missing 'tag' parameter
    invalid_plan_json = json.dumps([{
        "step": "Tag a function",
        "action": "add_capability_tag",
        "params": {
            "file_path": "src/test.py",
            "symbol_name": "test_func"
            # 'tag' is missing
        }
    }])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{invalid_plan_json}\n```"

    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        plan = agent.create_execution_plan(goal)

    # Pydantic validation should fail, resulting in an empty plan
    assert plan == []

@pytest.mark.asyncio
async def test_execute_plan_calls_dispatcher(mock_dependencies):
    """Tests that execute_plan correctly dispatches a valid task."""
    agent = PlannerAgent(**mock_dependencies)
    
    # We create a valid ExecutionTask object directly
    task = ExecutionTask(
        step="Test Step",
        action="add_capability_tag",
        params={"file_path": "test.py", "symbol_name": "test_func", "tag": "test_tag"}
    )
    plan = [task]
    
    # We mock the dispatcher's target method to see if it gets called
    agent._execute_add_tag = AsyncMock()
    
    success, message = await agent.execute_plan(plan)
    
    assert success is True
    agent._execute_add_tag.assert_awaited_once_with(task.params, task.step)