from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.execution_agent import ExecutionAgent


# ID: f18b1a2a-2ba4-4a1b-ba5e-181b57315363
def test_ExecutionAgent_execute_plan():
    # Build the agent under test with mocked dependencies
    mock_executor = MagicMock()
    agent = ExecutionAgent(executor=mock_executor, write=True)
    agent.tracer = MagicMock()

    # Construct a simple happy-path plan with one successful step
    step = MagicMock()
    step.action = "file.create"
    step.description = "Create a new module"
    step.is_critical = True
    step.metadata = {}
    step.params = {"file_path": "out.py", "code": "print('hi')\n"}

    detailed_plan = MagicMock()
    detailed_plan.steps = [step]
    detailed_plan.step_count = 1
    detailed_plan.goal = "Build a module"

    ok_result = MagicMock()
    ok_result.ok = True
    ok_result.data = {}

    agent._execute_step = AsyncMock(return_value=ok_result)

    with patch(
        "will.agents.execution_agent._params_to_dict",
        return_value={"file_path": "out.py", "code": "print('hi')\n"},
    ):
        import asyncio

        results = asyncio.run(agent.execute_plan(detailed_plan))

    # Happy path: no failures, files captured, no errors
    assert results.success is True
    assert results.errors == []
    assert "out.py" in results.files_written
    agent._execute_step.assert_awaited_once_with(step, 1)
    agent.tracer.record.assert_called_once()


# ID: 27dcb9e4-9a09-417c-a3e3-6651a94aa3da
def test_ExecutionAgent():
    executor = MagicMock()
    executor.execute = AsyncMock()

    agent = ExecutionAgent(executor=executor, write=False)

    assert agent.executor is executor
    assert agent.write is False
    assert agent.tracer is not None


import pytest


@pytest.mark.asyncio
# ID: f81aa73b-6434-4530-b372-2e31c57d2104
async def test_execution_agent_execute_plan():
    from will.agents.execution_agent import ExecutionAgent

    executor = MagicMock()
    agent = ExecutionAgent(executor=executor, write=True)

    agent.tracer = MagicMock()

    params = MagicMock()
    params.model_dump = MagicMock(
        return_value={"file_path": "a.py", "code": "print(1)"}
    )

    step = MagicMock()
    step.action = "file.create"
    step.description = "create file"
    step.is_critical = True
    step.metadata = {}
    step.params = params

    detailed_plan = MagicMock()
    detailed_plan.step_count = 1
    detailed_plan.steps = [step]
    detailed_plan.goal = "do the thing"

    action_result = MagicMock()
    action_result.ok = True
    action_result.data = {}

    agent._execute_step = AsyncMock(return_value=action_result)

    with patch(
        "will.agents.execution_agent._params_to_dict",
        return_value={"file_path": "a.py", "code": "print(1)"},
    ):
        result = await agent.execute_plan(detailed_plan)

    agent._execute_step.assert_awaited_once_with(step, 1)
    assert result.success is True
    assert result.files_written == ["a.py"]
    assert result.errors == []
    assert result.warnings == []
    agent.tracer.record.assert_called_once()
