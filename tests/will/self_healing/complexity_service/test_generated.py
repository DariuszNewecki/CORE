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


from pathlib import Path
from types import SimpleNamespace


# ID: 344467d1-67c2-437c-af91-89630fd11832
def test_ComplexityRemediationService_remediate():
    repo_path = Path("/repo")
    file_path = repo_path / "pkg" / "mod.py"
    real_path_cls = Path

    git_service = MagicMock()
    git_service.repo_path = repo_path

    context = SimpleNamespace(
        path_resolver=MagicMock(),
        git_service=git_service,
        action_executor=MagicMock(),
    )

    read_text_mock = MagicMock(return_value="original code")

    with (
        patch("will.self_healing.complexity_service.DecisionTracer") as tracer_cls,
        patch("will.self_healing.complexity_service.FileAnalyzer") as analyzer_cls,
        patch(
            "will.self_healing.complexity_service.ComplexityStrategist"
        ) as strategist_cls,
        patch("will.self_healing.complexity_service.LimbWorkspace") as workspace_cls,
        patch("will.self_healing.complexity_service.ExecutionAgent") as agent_cls,
    ):
        tracer_cls.return_value = MagicMock()

        analyzer = MagicMock()
        analyzer.execute = AsyncMock(
            return_value=SimpleNamespace(
                ok=True,
                data={},
                metadata={"total_definitions": 3},
            )
        )
        analyzer_cls.return_value = analyzer

        strategist = MagicMock()
        strategist.execute = AsyncMock(
            return_value=SimpleNamespace(data={"strategy": "extract"})
        )
        strategist_cls.return_value = strategist

        workspace_cls.return_value = MagicMock()

        agent = MagicMock()
        agent.execute_plan = AsyncMock(return_value=SimpleNamespace(success=True))
        agent_cls.return_value = agent

        service = ComplexityRemediationService(context)
        service._run_reflex_loop = AsyncMock(return_value={"path": "new code"})
        service._build_execution_blueprint = MagicMock(return_value={"plan": "x"})

        # ID: fa0acd31-20e3-4d9f-a541-10adba2afbfa
        def fake_read_text(self, *args, **kwargs):
            return read_text_mock(self, *args, **kwargs)

        with patch.object(Path, "read_text", fake_read_text):
            result = asyncio.run(service.remediate(file_path, write=False))

    assert result is True
    analyzer.execute.assert_awaited_once()
    strategist.execute.assert_awaited_once_with(complexity_score=3)
    agent.execute_plan.assert_awaited_once()
    service._run_reflex_loop.assert_awaited_once()
    service._build_execution_blueprint.assert_called_once()
