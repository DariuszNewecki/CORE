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
