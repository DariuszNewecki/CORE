from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.self_healing.clarity_service import remediate_clarity_v2


@pytest.mark.asyncio
# ID: 2702c2da-e060-4066-9b42-e6e67d72ba71
async def test_remediate_clarity_v2():
    context = MagicMock()
    context.git_service.repo_path = "/tmp/repo"
    context.cognitive_service = MagicMock()
    context.cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())

    file_path = Path("/tmp/repo/src/foo.py")

    interp_result = MagicMock()
    interp_result.data = {"task": MagicMock(targets=["src/foo.py"])}

    analyzer_result = MagicMock()
    analyzer_result.ok = True
    analyzer_result.metadata = {"line_count": 10, "total_definitions": 2}

    strategy_result = MagicMock()
    strategy_result.data = {"strategy": "extract_method", "instruction": "do it"}

    verdict_result = MagicMock()
    verdict_result.ok = True
    verdict_result.data = {"is_better": True, "improvement_ratio": 0.5}

    auth_result = MagicMock()
    auth_result.data = {"can_proceed": True, "blockers": []}

    mock_interp = MagicMock()
    mock_interp.execute = AsyncMock(return_value=interp_result)

    mock_analyzer = MagicMock()
    mock_analyzer.execute = AsyncMock(return_value=analyzer_result)

    mock_strategist = MagicMock()
    mock_strategist.execute = AsyncMock(return_value=strategy_result)

    mock_evaluator = MagicMock()
    mock_evaluator.execute = AsyncMock(return_value=verdict_result)

    mock_decider = MagicMock()
    mock_decider.execute = AsyncMock(return_value=auth_result)

    mock_model = MagicMock()
    mock_model.manifest = MagicMock(role="coder")
    mock_model.invoke = AsyncMock(return_value="def foo():\n    return 1\n")

    with (
        patch(
            "will.self_healing.clarity_service.CLIArgsInterpreter",
            return_value=mock_interp,
        ),
        patch(
            "will.self_healing.clarity_service.FileAnalyzer",
            return_value=mock_analyzer,
        ),
        patch(
            "will.self_healing.clarity_service.ClarityStrategist",
            return_value=mock_strategist,
        ),
        patch(
            "will.self_healing.clarity_service.ClarityEvaluator",
            return_value=mock_evaluator,
        ),
        patch(
            "will.self_healing.clarity_service.GovernanceDecider",
            return_value=mock_decider,
        ),
        patch(
            "will.self_healing.clarity_service.PromptModel.load",
            return_value=mock_model,
        ),
        patch(
            "will.self_healing.clarity_service.extract_python_code_from_response",
            return_value="def foo():\n    return 2\n",
        ),
        patch(
            "pathlib.Path.read_text",
            return_value="def foo():\n    return 1\n",
        ),
    ):
        await remediate_clarity_v2(context, file_path, write=False)

    mock_interp.execute.assert_awaited_once()
    mock_analyzer.execute.assert_awaited_once()
    mock_strategist.execute.assert_awaited_once()
    mock_evaluator.execute.assert_awaited_once()
    mock_decider.execute.assert_awaited_once()
    mock_model.invoke.assert_awaited_once()
