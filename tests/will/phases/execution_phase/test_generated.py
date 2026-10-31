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
