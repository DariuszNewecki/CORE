# tests/unit/test_planner_agent.py
import json
import pytest
import textwrap
from agents.planner_agent import PlannerAgent, ExecutionTask, PlannerConfig, PlanExecutionError
from agents.plan_executor import PlanExecutor
from agents.models import TaskParams
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
        "config": PlannerConfig(auto_commit=True)
    }

def test_create_execution_plan_success(mock_dependencies):
    """Tests that the planner can successfully parse a valid high-level plan."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Test goal"
    
    plan_json = json.dumps([{
        "step": "A valid step",
        "action": "create_file",
        "params": { "file_path": "src/test.py" }
    }])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{plan_json}\n```"

    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        plan = agent.create_execution_plan(goal)

    assert len(plan) == 1
    assert isinstance(plan[0], ExecutionTask)
    assert plan[0].action == "create_file"

def test_create_execution_plan_fails_on_invalid_action(mock_dependencies):
    """Tests that the planner fails if the plan contains an invalid action."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Test goal"
    
    invalid_plan_json = json.dumps([{"step": "Invalid action", "action": "make_coffee", "params": {}}])
    mock_dependencies["orchestrator_client"].make_request.return_value = f"```json\n{invalid_plan_json}\n```"

    with patch('core.prompt_pipeline.PromptPipeline.process', return_value="enriched_prompt"):
        with pytest.raises(PlanExecutionError):
            agent.create_execution_plan(goal)

@pytest.mark.asyncio
async def test_execute_plan_full_flow(mock_dependencies):
    """Tests the new two-step execute_plan flow."""
    agent = PlannerAgent(**mock_dependencies)
    goal = "Create a hello world file"

    plan_json = json.dumps([{"step": "Create the file", "action": "create_file", "params": {"file_path": "hello.py"}}])
    agent.orchestrator.make_request.return_value = f"```json\n{plan_json}\n```"
    agent.generator.make_request.return_value = "print('Hello, World!')"

    agent.executor.execute_plan = AsyncMock()
    
    success, message = await agent.execute_plan(goal)

    assert success is True
    assert message == "✅ Plan executed successfully."
    agent.executor.execute_plan.assert_awaited_once()
    
    executed_plan = agent.executor.execute_plan.call_args[0][0]
    assert executed_plan[0].params.code == "print('Hello, World!')"


@pytest.mark.asyncio
@patch('agents.plan_executor.validate_code')
async def test_plan_executor_create_file_success(mock_validate_code, mock_dependencies, tmp_path):
    """Happy Path: Verifies that a valid 'create_file' task succeeds via the executor."""
    mock_validate_code.return_value = {"status": "clean", "code": "print('hello world')", "violations": []}
    
    executor = PlanExecutor(
        file_handler=mock_dependencies["file_handler"],
        git_service=mock_dependencies["git_service"],
        config=mock_dependencies["config"]
    )
    executor.repo_path = tmp_path

    params = TaskParams(file_path="src/new_feature.py", code="print('hello world')")
    
    await executor._execute_create_file(params)
    
    mock_validate_code.assert_called_once_with("src/new_feature.py", "print('hello world')")
    executor.file_handler.add_pending_write.assert_called_once()
    executor.git_service.commit.assert_called_once()


@pytest.mark.asyncio
@patch('agents.plan_executor.validate_code')
async def test_plan_executor_create_file_fails_on_validation_error(mock_validate_code, mock_dependencies):
    """Sad Path: Verifies that the task fails if the code has 'error' severity violations."""
    mock_validate_code.return_value = {
        "status": "dirty",
        "violations": [{"rule": "E999", "message": "Syntax error!", "line": 1, "severity": "error"}],
        "code": "print("
    }
    executor = PlanExecutor(**{k: v for k, v in mock_dependencies.items() if k not in ['orchestrator_client', 'generator_client', 'intent_guard']})
    params = TaskParams(file_path="src/bad_file.py", code="print(")
    
    with pytest.raises(PlanExecutionError, match="failed validation") as excinfo:
        await executor._execute_create_file(params)
    
    assert len(excinfo.value.violations) == 1
    assert excinfo.value.violations[0]["rule"] == "E999"

@pytest.mark.asyncio
async def test_plan_executor_create_file_fails_if_file_exists(mock_dependencies, tmp_path):
    """Sad Path: Verifies that the task fails if the target file already exists."""
    executor = PlanExecutor(**{k: v for k, v in mock_dependencies.items() if k not in ['orchestrator_client', 'generator_client', 'intent_guard']})
    executor.repo_path = tmp_path

    existing_file_path = tmp_path / "src/already_exists.py"
    existing_file_path.parent.mkdir(exist_ok=True)
    existing_file_path.touch()
    
    params = TaskParams(file_path="src/already_exists.py", code="print('overwrite?')")
    
    with pytest.raises(FileExistsError):
        await executor._execute_create_file(params)

@pytest.mark.asyncio
@patch('agents.plan_executor.validate_code')
@patch('agents.plan_executor.CodeEditor')
async def test_plan_executor_edit_function_success(mock_code_editor_class, mock_validate_code, mock_dependencies, tmp_path):
    """Happy Path: Verifies that a valid 'edit_function' task succeeds via the executor."""
    mock_editor_instance = mock_code_editor_class.return_value
    mock_validate_code.return_value = {"status": "clean", "code": 'def my_func():\n    # A new comment\n    return 2\n', "violations": []}
    
    executor = PlanExecutor(
        file_handler=mock_dependencies["file_handler"],
        git_service=mock_dependencies["git_service"],
        config=mock_dependencies["config"]
    )
    executor.repo_path = tmp_path
    
    original_code = textwrap.dedent("""
        def my_func():
            return 1
    """)
    target_file = tmp_path / "src/feature.py"
    target_file.parent.mkdir(exist_ok=True)
    target_file.write_text(original_code)
    
    new_function_code = textwrap.dedent("""
        def my_func():
            # A new comment
            return 2
    """)
    validated_and_formatted_snippet = 'def my_func():\n    # A new comment\n    return 2\n'
    
    params = TaskParams(
        file_path="src/feature.py",
        symbol_name="my_func",
        code=new_function_code
    )

    await executor._execute_edit_function(params)

    mock_validate_code.assert_called_once_with("src/feature.py", new_function_code)
    
    mock_editor_instance.replace_symbol_in_code.assert_called_once_with(
        original_code,
        "my_func",
        validated_and_formatted_snippet
    )
    
    executor.file_handler.add_pending_write.assert_called_once()
    executor.git_service.commit.assert_called_once_with("feat: Modify function my_func in src/feature.py")