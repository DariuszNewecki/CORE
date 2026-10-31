from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate


# ID: 51072a4d-f2c4-430b-a141-ded3e72f2f84
async def test_TestGenCognitiveDelegate_execute_cognitive_step() -> None:
    core_context = MagicMock()
    delegate = TestGenCognitiveDelegate(core_context)

    expected_result = {"test_code": "def test_sample():\n    assert True\n"}

    with patch.object(
        delegate,
        "_generate_test_snippet",
        new=AsyncMock(return_value=expected_result),
    ) as mock_generate:
        params = {"requirement": "some requirement"}
        result = await delegate.execute_cognitive_step(
            step_ref="generate.test_snippet",
            params=params,
        )

    mock_generate.assert_awaited_once_with(params)
    assert result == expected_result


from pathlib import Path


# ID: fb182680-1871-4e2a-85a7-cb11f5267db2
def test_TestGenCognitiveDelegate():
    import asyncio

    core_context = MagicMock()
    core_context.git_service.repo_path = Path("/repo")
    core_context.cognitive_service = MagicMock()

    delegate = TestGenCognitiveDelegate(core_context)
    delegate._agent = MagicMock()
    delegate._agent.generate = AsyncMock(return_value="def test_x():\n    assert True")

    params = {
        "source_file": "src/pkg/module.py",
        "symbol_name": "my_func",
        "signature": "def my_func() -> None",
    }

    fake_source_path = MagicMock()
    fake_source_path.exists.return_value = False

    fake_repo_root = MagicMock(spec=Path)
    fake_repo_root.__truediv__ = MagicMock(return_value=fake_source_path)
    core_context.git_service.repo_path = fake_repo_root

    with (
        patch(
            "will.agents.test_gen_cognitive_delegate.source_to_test_path",
            return_value="tests/test_module.py",
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.extract_symbol_code",
            return_value="def my_func() -> None:\n    pass",
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.extract_referenced_module_constants",
            return_value="",
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.derive_module_path",
            return_value="pkg.module",
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.IntentGuardAcceptanceCondition",
            return_value=MagicMock(),
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.PytestAcceptanceCondition",
            return_value=MagicMock(),
        ),
        patch(
            "will.agents.test_gen_cognitive_delegate.CompositeAcceptanceCondition",
            return_value=MagicMock(),
        ),
        patch(
            "body.atomic.executor.ActionExecutor",
            return_value=MagicMock(),
        ),
    ):
        result = asyncio.run(
            delegate.execute_cognitive_step("generate.test_snippet", params)
        )

    assert result == {"generated_code": "def test_x():\n    assert True"}
    delegate._agent.generate.assert_awaited_once()
