from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.complexity_service import ComplexityRemediationService


# ID: d2c47a1c-f5f9-43e0-ba3d-7bc997a7b6c9
def test_ComplexityRemediationService(tmp_path):
    context = MagicMock()
    repo_path = tmp_path
    context.git_service.repo_path = repo_path

    # Ensure DecisionTracer's path_resolver points at a real directory.
    context.path_resolver.repo_root = repo_path

    target_file = repo_path / "sample.py"
    target_file.write_text("def f():\n    return 1\n", encoding="utf-8")

    with patch(
        "will.self_healing.complexity_service.DecisionTracer"
    ) as mock_tracer_cls:
        mock_tracer_cls.return_value = MagicMock()
        service = ComplexityRemediationService(context=context)

    assert service.context is context
    assert service.tracer is mock_tracer_cls.return_value

    analysis_result = MagicMock()
    analysis_result.ok = True
    analysis_result.data = {}
    analysis_result.metadata = {"total_definitions": 5}

    mock_analyzer = MagicMock()
    mock_analyzer.execute = AsyncMock(return_value=analysis_result)

    strategy_res = MagicMock()
    strategy_res.data = {"instruction": "split into helpers"}

    mock_strategist = MagicMock()
    mock_strategist.execute = AsyncMock(return_value=strategy_res)

    final_code_map = {"sample.py": "def f():\n    return 1\n"}
    blueprint = MagicMock()

    exec_results = MagicMock()
    exec_results.success = True

    mock_agent = MagicMock()
    mock_agent.execute_plan = AsyncMock(return_value=exec_results)

    with (
        patch(
            "will.self_healing.complexity_service.FileAnalyzer",
            return_value=mock_analyzer,
        ),
        patch(
            "will.self_healing.complexity_service.ComplexityStrategist",
            return_value=mock_strategist,
        ),
        patch(
            "will.self_healing.complexity_service.LimbWorkspace",
            return_value=MagicMock(),
        ),
        patch(
            "will.self_healing.complexity_service.ExecutionAgent",
            return_value=mock_agent,
        ),
        patch.object(
            ComplexityRemediationService,
            "_run_reflex_loop",
            new=AsyncMock(return_value=final_code_map),
        ),
        patch.object(
            ComplexityRemediationService,
            "_build_execution_blueprint",
            return_value=blueprint,
        ),
    ):
        context.action_executor = MagicMock()
        result = asyncio.new_event_loop().run_until_complete(
            service.remediate(file_path=target_file, write=False)
        )

    assert result is True
    mock_analyzer.execute.assert_awaited_once_with(file_path="sample.py")
    mock_strategist.execute.assert_awaited_once_with(complexity_score=5)
    mock_agent.execute_plan.assert_awaited_once_with(blueprint)
