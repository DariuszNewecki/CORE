from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.phases.runtime_phase import RuntimePhase


# ID: ca8b452f-9cac-44b5-b8a4-4f17cfc9a4ea
async def test_RuntimePhase_execute():

    core_context = MagicMock()
    phase = RuntimePhase.__new__(RuntimePhase)
    phase.context = core_context
    phase._code_gen = MagicMock()
    phase._test_gen = MagicMock()
    phase._investigation = MagicMock()

    sub_result = MagicMock()
    sub_result.ok = True
    sub_result.data = {"some": "data"}
    sub_result.error = ""
    phase._code_gen.execute = AsyncMock(return_value=sub_result)

    context = MagicMock()
    context.workflow_type = "code_modification"
    context.results = {}

    result = await RuntimePhase.execute(phase, context)

    assert result.ok is True
    assert result.name == "runtime"
    assert result.data["candidate_outputs_produced"] is True
    assert result.data["code_generation"] == {"some": "data"}
    assert context.results["code_generation"] == {"some": "data"}
    phase._code_gen.execute.assert_awaited_once_with(context)
