from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.code_generation.code_generator import CodeGenerator


# ID: 2bb834bb-a6ed-4cc3-9dcd-48731eb5bf8c
def test_CodeGenerator():
    cognitive_service = MagicMock()
    generator_client = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=generator_client)

    path_resolver = MagicMock()
    path_resolver.repo_root = MagicMock()

    prompt_pipeline = MagicMock()
    prompt_pipeline.process = MagicMock(return_value="enriched prompt")

    tracer = MagicMock()
    tracer.record = MagicMock()

    task = MagicMock()
    task.step = "generate hello function"
    task.task_type = "code_generation"
    task.params.file_path = "src/example.py"
    task.params.symbol_name = "hello"

    with patch(
        "will.agents.code_generation.code_generator.PromptModel"
    ) as mock_prompt_model:
        code_gen_model = MagicMock()
        code_gen_model.manifest.role = "coder"
        code_gen_model.invoke = AsyncMock(
            return_value="def hello():\n    return 'world'\n"
        )
        mock_prompt_model.load.return_value = code_gen_model

        code_generator = CodeGenerator(
            cognitive_service=cognitive_service,
            path_resolver=path_resolver,
            prompt_pipeline=prompt_pipeline,
            tracer=tracer,
            context_service=None,
        )

        with (
            patch(
                "will.agents.code_generation.code_generator.build_standard_prompt",
                return_value="standard prompt",
            ),
            patch(
                "will.agents.code_generation.code_generator.extract_code_constitutionally",
                return_value="def hello():\n    return 'world'\n",
            ),
            patch(
                "will.agents.code_generation.code_generator.repair_basic_syntax",
                return_value="def hello():\n    return 'world'\n",
            ),
        ):
            result = __import__("asyncio").run(
                code_generator.generate_code(
                    task=task,
                    goal="Generate hello function",
                    context_str="context",
                    pattern_id="pattern-1",
                    pattern_requirements="requirements",
                )
            )

    assert result == "def hello():\n    return 'world'\n"
    prompt_pipeline.process.assert_called_once_with("standard prompt")
    assert tracer.record.called


import pytest


@pytest.mark.asyncio
# ID: 06044d5d-cc6a-4888-a534-1dbbd71cf1e1
async def test_CodeGenerator_generate_code():
    from will.agents.code_generation.code_generator import CodeGenerator

    cognitive_service = MagicMock()
    generator_client = MagicMock()
    generator_client.__class__ = type("FakeClient", (), {})
    cognitive_service.aget_client_for_role = AsyncMock(return_value=generator_client)

    path_resolver = MagicMock()
    path_resolver.repo_root = MagicMock()

    prompt_pipeline = MagicMock()
    prompt_pipeline.process = MagicMock(return_value="enriched prompt")

    tracer = MagicMock()
    tracer.record = MagicMock()

    code_gen_model = MagicMock()
    code_gen_model.manifest = MagicMock()
    code_gen_model.manifest.role = "coder"
    code_gen_model.invoke = AsyncMock(return_value="print('hello world')")

    test_gen_model = MagicMock()

    task = MagicMock()
    task.step = "generate hello"
    task.task_type = "code_generation"
    task.params = MagicMock()
    task.params.file_path = "hello.py"
    task.params.symbol_name = "hello"

    with patch(
        "will.agents.code_generation.code_generator.PromptModel.load",
        side_effect=lambda *a, **k: code_gen_model,
    ):
        generator = CodeGenerator(
            cognitive_service=cognitive_service,
            path_resolver=path_resolver,
            prompt_pipeline=prompt_pipeline,
            tracer=tracer,
        )

    generator._code_gen_model = code_gen_model
    generator._test_gen_model = test_gen_model

    with (
        patch(
            "will.agents.code_generation.code_generator.build_standard_prompt",
            return_value="standard prompt",
        ),
        patch(
            "will.agents.code_generation.code_generator.extract_code_constitutionally",
            return_value="print('hello world')",
        ),
        patch(
            "will.agents.code_generation.code_generator.repair_basic_syntax",
            side_effect=lambda code: code,
        ),
    ):
        result = await generator.generate_code(
            task=task,
            goal="say hello",
            context_str="some context",
            pattern_id="p1",
            pattern_requirements="reqs",
        )

    assert result == "print('hello world')"
    code_gen_model.invoke.assert_awaited_once()
