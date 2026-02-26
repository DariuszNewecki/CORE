# tests/will/agents/test_plan_executor.py

import pytest


pytestmark = pytest.mark.legacy

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from shared.models import ExecutionTask, PlanExecutionError, TaskParams
from will.agents.plan_executor import PlanExecutor


class DummyHandler:
    def __init__(self):
        self.called = False
        self.params_received = None
        self.context_received = None

    async def execute(self, params, context):
        self.called = True
        self.params_received = params
        self.context_received = context
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_execute_plan_success(mocker, tmp_path):
    dummy_handler = DummyHandler()
    mock_registry = MagicMock()
    mock_registry.get_handler.return_value = dummy_handler
    mocker.patch("will.agents.plan_executor.ActionRegistry", return_value=mock_registry)

    file_handler = MagicMock()
    file_handler.repo_path = tmp_path
    git_service = MagicMock()
    config = SimpleNamespace(task_timeout=5)

    executor = PlanExecutor(file_handler, git_service, config)
    params = TaskParams(file_path="file.py", code="print('x')")
    task = ExecutionTask(step="Step 1", action="test_action", params=params)

    await executor.execute_plan([task])

    assert dummy_handler.called
    mock_registry.get_handler.assert_called_with("test_action")


@pytest.mark.asyncio
async def test_execute_plan_skips_missing_handler(mocker, tmp_path):
    mock_registry = MagicMock()
    mock_registry.get_handler.return_value = None
    mocker.patch("will.agents.plan_executor.ActionRegistry", return_value=mock_registry)

    file_handler = MagicMock()
    file_handler.repo_path = tmp_path
    git_service = MagicMock()
    config = SimpleNamespace(task_timeout=5)

    executor = PlanExecutor(file_handler, git_service, config)
    params = TaskParams(file_path="a.py", code="x=1")
    task = ExecutionTask(step="No handler", action="missing", params=params)

    await executor.execute_plan([task])
    mock_registry.get_handler.assert_called_once_with("missing")


@pytest.mark.asyncio
async def test_execute_task_timeout(tmp_path):
    handler = DummyHandler()

    async def slow_execute(params, context):
        await asyncio.sleep(0.2)

    handler.execute = slow_execute
    file_handler = MagicMock()
    file_handler.repo_path = tmp_path
    git_service = MagicMock()
    config = SimpleNamespace(task_timeout=0.05)
    executor = PlanExecutor(file_handler, git_service, config)

    task = ExecutionTask(step="Slow step", action="dummy", params=TaskParams())
    with pytest.raises(PlanExecutionError) as exc:
        await executor._execute_task_with_timeout(task, handler)
    assert "timed out" in str(exc.value)


@pytest.mark.asyncio
async def test_execute_task_generic_exception(tmp_path):
    handler = DummyHandler()

    async def fail(params, context):
        raise RuntimeError("boom")

    handler.execute = fail
    file_handler = MagicMock()
    file_handler.repo_path = tmp_path
    git_service = MagicMock()
    config = SimpleNamespace(task_timeout=5)
    executor = PlanExecutor(file_handler, git_service, config)

    task = ExecutionTask(step="Fail step", action="oops", params=TaskParams())
    with pytest.raises(PlanExecutionError) as exc:
        await executor._execute_task_with_timeout(task, handler)
    assert "failed" in str(exc.value)


@pytest.mark.asyncio
async def test_execute_plan_multiple_tasks(mocker, tmp_path):
    mock_registry = MagicMock()
    handler1, handler2 = DummyHandler(), DummyHandler()
    mock_registry.get_handler.side_effect = [handler1, handler2]

    mocker.patch("will.agents.plan_executor.ActionRegistry", return_value=mock_registry)

    file_handler = MagicMock()
    file_handler.repo_path = tmp_path
    git_service = MagicMock()
    config = SimpleNamespace(task_timeout=5)
    executor = PlanExecutor(file_handler, git_service, config)

    t1 = ExecutionTask(step="S1", action="a1", params=TaskParams())
    t2 = ExecutionTask(step="S2", action="a2", params=TaskParams())
    await executor.execute_plan([t1, t2])

    assert handler1.called and handler2.called
    assert mock_registry.get_handler.call_count == 2
