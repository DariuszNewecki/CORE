from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from will.phases.execution_phase import ExecutionPhase


# ID: 0940cd19-d331-4046-b757-79b503b7cf99
async def test_ExecutionPhase():
    # Happy path: write=False dry-run with a detailed_plan present
    context = MagicMock()
    phase = ExecutionPhase(context)

    step = SimpleNamespace()
    detailed_plan = SimpleNamespace(steps=[step, step])
    ctx = SimpleNamespace(
        write=False,
        results={"code_generation": {"detailed_plan": detailed_plan}},
    )

    result = await phase.execute(ctx)

    assert result.name == "execution"
    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["steps_planned"] == 2
    assert result.data["files_written"] == []
    assert result.duration_sec >= 0


from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
# ID: feb164c6-f401-4cb2-b037-15ca3e2ac189
async def test_ExecutionPhase_execute():
    context = MagicMock()
    phase = ExecutionPhase(context=context)

    detailed_plan = MagicMock()
    detailed_plan.steps = [MagicMock(), MagicMock()]

    ctx = MagicMock()
    ctx.write = True
    ctx.results = {"code_generation": {"detailed_plan": detailed_plan}}

    exec_results = MagicMock()
    exec_results.success = True
    exec_results.files_written = ["a.py", "b.py"]
    exec_results.errors = []
    exec_results.warnings = []

    mock_agent = MagicMock()
    mock_agent.execute_plan = AsyncMock(return_value=exec_results)

    with (
        patch(
            "will.phases.execution_phase.ExecutionAgent",
            return_value=mock_agent,
        ),
        patch("will.phases.execution_phase.ActionExecutor") as mock_executor_cls,
    ):
        result = await phase.execute(ctx)

    mock_executor_cls.assert_called_once_with(context)
    mock_agent.execute_plan.assert_awaited_once_with(detailed_plan)

    assert result.name == "execution"
    assert result.ok is True
    assert result.error == ""
    assert result.data["files_written"] == ["a.py", "b.py"]
    assert result.data["errors_count"] == 0
    assert result.data["warnings_count"] == 0
