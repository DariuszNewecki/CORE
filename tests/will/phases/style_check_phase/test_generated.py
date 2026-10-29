from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.phases.style_check_phase import StyleCheckPhase


# ID: e81b748d-693d-41d1-86fd-7bd5b2777b84
async def test_StyleCheckPhase_execute():
    core_context = MagicMock()
    core_context.auditor_context = MagicMock()

    phase = StyleCheckPhase(core_context)
    phase.context = core_context
    phase.tracer = MagicMock()
    phase._extract_steps = MagicMock(return_value=[{"step": 1}])
    phase._get_step_params = MagicMock(
        return_value={"file_path": "foo.py", "code": "x = 1\n"}
    )
    phase._get_param = MagicMock(side_effect=lambda params, key: params.get(key))

    context = MagicMock()
    context.results = {"code_generation": {"steps": [{"step": 1}]}}

    val_result = {"status": "clean", "violations": []}
    with patch(
        "will.phases.style_check_phase.validate_code_async",
        new=AsyncMock(return_value=val_result),
    ):
        result = await phase.execute(context)

    assert result.ok is True
    assert result.name == "style_check"
    assert result.data["violations"] == 0
    assert result.data["files_checked"] == 1
