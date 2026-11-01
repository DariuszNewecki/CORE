from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from will.phases.interpret_phase import InterpretPhase


@pytest.mark.asyncio
# ID: 0b74b4f5-46b4-4b57-affb-3288c4c454e6
async def test_InterpretPhase_execute():
    context = MagicMock()

    phase = InterpretPhase.__new__(InterpretPhase)
    phase.context = context
    phase._infer_workflow_type = MagicMock(return_value="code_modification")
    phase._extract_target_info = MagicMock(
        return_value={"targets": ["src/foo.py"], "constraints": {"lint": True}}
    )
    phase._is_confident = MagicMock(return_value=True)

    workflow_context = MagicMock()
    workflow_context.goal = "Refactor the foo module for modularity"
    workflow_context.workflow_type = "code_modification"

    result = await InterpretPhase.execute(phase, workflow_context)

    assert result.ok is True
    assert result.name == "interpret"
    assert result.data["goal"] == "Refactor the foo module for modularity"
    assert result.data["workflow_type"] == "code_modification"
    assert result.data["targets"] == ["src/foo.py"]
    assert result.data["constraints"] == {"lint": True}
    assert result.data["clarification_needed"] is False
    assert result.data["_metadata"]["interpretation_method"] == "explicit"
    assert result.data["_metadata"]["confidence"] == "high"

    phase._infer_workflow_type.assert_not_called()
    phase._extract_target_info.assert_called_once_with(
        "Refactor the foo module for modularity"
    )





# ID: 83580088-4af8-40e6-a895-6a97291484b1
def test_InterpretPhase():
    context = MagicMock()
    phase = InterpretPhase(context)

    workflow_context = MagicMock()
    workflow_context.goal = "Refactor the user_service module to improve modularity"
    workflow_context.workflow_type = "refactor_modularity"

    import asyncio

    result = asyncio.run(phase.execute(workflow_context))

    assert result.name == "interpret"
    assert result.ok is True
    assert result.data["workflow_type"] == "refactor_modularity"
    assert result.data["goal"] == workflow_context.goal
    assert result.data["clarification_needed"] is False
    assert result.data["_metadata"]["interpretation_method"] == "explicit"
    assert "user_service" in result.data["targets"]
