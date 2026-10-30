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



import pytest


@pytest.mark.asyncio
# ID: 7627009c-dcc5-4c39-9acc-cb8376289b2f
async def test_TestGenerationPhase() -> None:
    core_context = MagicMock()
    phase = TestGenerationPhase(core_context)

    phase.tracer = MagicMock()
    phase.tracer.record = MagicMock()

    detailed_plan = {
        "steps": [
            {"params": {"file_path": "src/will/foo.py"}},
            {"params": {"file_path": "src/tests/test_foo.py"}},
            {"params": {"file_path": "docs/readme.md"}},
            {"params": {"file_path": "src/will/bar.py"}},
        ]
    }

    workflow_context = MagicMock()
    workflow_context.workflow_type = "full_feature_development"
    workflow_context.results = {
        "code_generation": {"data": {"detailed_plan": detailed_plan}}
    }

    result = await phase.execute(workflow_context)

    assert result.ok is True
    assert result.name == "test_generation"
    assert result.data["tests_generated"] == 0
    assert result.data["target_files"] == ["src/will/foo.py", "src/will/bar.py"]
    assert "note" in result.data

    phase.tracer.record.assert_called_once()
    _, kwargs = phase.tracer.record.call_args
    assert kwargs.get("chosen_action") == "test_generation_stub"
