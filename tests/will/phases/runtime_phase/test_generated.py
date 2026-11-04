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


from unittest.mock import patch


# ID: 0db23b70-80dd-41e6-b7d2-c21f234a66a4
async def test_RuntimePhase():
    core_context = MagicMock()
    with (
        patch("will.phases.runtime_phase.CodeGenerationPhase") as mock_code_gen_cls,
        patch("will.phases.runtime_phase.TestGenerationPhase") as mock_test_gen_cls,
        patch("will.phases.runtime_phase.InvestigationPhase") as mock_inv_cls,
    ):
        mock_code_gen = MagicMock()
        mock_code_gen.execute = AsyncMock(
            return_value=MagicMock(ok=True, data={"gen": "ok"}, error="")
        )
        mock_code_gen_cls.return_value = mock_code_gen

        mock_test_gen = MagicMock()
        mock_test_gen.execute = AsyncMock(
            return_value=MagicMock(ok=True, data={"test": "ok"}, error="")
        )
        mock_test_gen_cls.return_value = mock_test_gen

        mock_inv = MagicMock()
        mock_inv.execute = AsyncMock(
            return_value=MagicMock(ok=True, data={"inv": "ok"}, error="")
        )
        mock_inv_cls.return_value = mock_inv

        phase = RuntimePhase(core_context)

        workflow_context = MagicMock()
        workflow_context.workflow_type = "code_modification"
        workflow_context.results = {}

        result = await phase.execute(workflow_context)

    assert result.ok is True
    assert result.name == "runtime"
    assert result.data["candidate_outputs_produced"] is True
    assert result.data["code_generation"] == {"gen": "ok"}
    mock_code_gen.execute.assert_awaited_once_with(workflow_context)
    assert workflow_context.results["code_generation"] == {"gen": "ok"}
