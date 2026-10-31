from __future__ import annotations

from unittest.mock import MagicMock


# ID: b1ff7297-e955-4eba-882a-789a2da1859d
async def test_LoadPhase_execute() -> None:
    from will.phases.load_phase import LoadPhase as _LoadPhase

    core_context = MagicMock()
    core_context.cognitive_service = MagicMock()
    core_context.file_handler = MagicMock()
    core_context.git_service = MagicMock()

    phase = _LoadPhase(core_context)

    workflow_context = MagicMock()
    workflow_context.write = False
    workflow_context.workflow_type = "action"
    workflow_context.results = {
        "parse": {
            "execution_plan": [
                {"action": "a"},
                {"action": "b"},
            ]
        }
    }

    result = await phase.execute(workflow_context)

    assert result.ok is True
    assert result.name == "load"
    assert result.data["execution_context_ready"] is True
    assert result.data["action_set_resolved"] is True
    assert result.data["steps"] == 2
    assert result.data["write_mode"] is False
    assert result.data["workflow_type"] == "action"
