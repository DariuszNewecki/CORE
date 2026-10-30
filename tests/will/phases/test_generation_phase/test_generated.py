from __future__ import annotations

from unittest.mock import MagicMock

from will.phases.test_generation_phase import TestGenerationPhase


# ID: 13a36d31-6e9c-4fd8-a140-fab2f69b2939
def test_TestGenerationPhaseexecute():
    core_context = MagicMock()
    phase = TestGenerationPhase(core_context)
    phase._extract_target_files = MagicMock(return_value=["a.py", "b.py"])
    phase.tracer = MagicMock()

    context = MagicMock()
    context.workflow_type = "feature"
    context.results = {
        "code_generation": {"data": {"detailed_plan": {"files": ["a.py", "b.py"]}}}
    }

    import asyncio

    result = asyncio.run(phase.execute(context))

    assert result.ok is True
    assert result.name == "test_generation"
    assert result.data["tests_generated"] == 0
    assert result.data["target_files"] == ["a.py", "b.py"]
    phase._extract_target_files.assert_called_once()
    phase.tracer.record.assert_called_once()
