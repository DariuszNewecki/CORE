"""Tests for CodeGenerator prompt routing by task_type.

Verifies that generate_code dispatches to the correct PromptModel depending
on task_type:
  - "test_generation" → _test_gen_model (test_gen_prompt) with context keys
    {module_path, goal, target_coverage}
  - all other task_types → _code_gen_model (code_generation_task_step_prompt)
    with context key {task_step}

This routing is the primary structural fix for the 98% build.tests failure
rate: the generic code_generation_task_step_prompt has no test-specific rules;
test_gen_prompt's system.txt enforces absolute imports, no hallucinated modules,
no placeholder bodies, and pytest asyncio_mode=auto constraints.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import body.atomic  # noqa: F401  -- body.atomic ↔ will.autonomy circular-import side effect
from shared.models.execution_models import ExecutionTask, TaskParams
from will.agents.code_generation.code_generator import CodeGenerator


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _make_generator() -> CodeGenerator:
    pipeline = MagicMock(name="PromptPipeline")
    pipeline.process.return_value = "ENRICHED_PROMPT"
    path_resolver = MagicMock(name="PathResolver")
    path_resolver.repo_root = _REPO_ROOT
    return CodeGenerator(
        cognitive_service=MagicMock(name="CognitiveService"),
        path_resolver=path_resolver,
        prompt_pipeline=pipeline,
        tracer=MagicMock(name="DecisionTracer"),
    )


def _task(task_type: str, file_path: str = "src/body/foo.py") -> ExecutionTask:
    return ExecutionTask(
        step="generate tests",
        action="generate",
        params=TaskParams(file_path=file_path, symbol_name=None),
        task_type=task_type,
    )


# ID: 794c36f3-a07d-4503-8c9e-c50714a8b71d
async def test_test_generation_invokes_test_gen_model() -> None:
    """task_type='test_generation' must call _test_gen_model.invoke with
    module_path/goal/target_coverage, never _code_gen_model.invoke."""
    cg = _make_generator()
    cg.cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    cg._test_gen_model.invoke = AsyncMock(return_value="def test_x():\n    assert True\n")
    cg._code_gen_model.invoke = AsyncMock(return_value="# must not be reached")

    await cg.generate_code(_task("test_generation"), "test goal", "ctx", "test_file", "")

    cg._test_gen_model.invoke.assert_awaited_once()
    ctx = cg._test_gen_model.invoke.call_args.kwargs.get("context", {})
    assert "module_path" in ctx, "module_path must be passed to test_gen_prompt"
    assert "goal" in ctx, "goal must be passed to test_gen_prompt"
    assert "target_coverage" in ctx, "target_coverage must be passed to test_gen_prompt"
    cg._code_gen_model.invoke.assert_not_awaited()


# ID: 2d78bc72-3fbf-441b-bcc9-06df67808e81
async def test_non_test_task_invokes_code_gen_model() -> None:
    """task_type other than 'test_generation' must call _code_gen_model.invoke
    with task_step, never _test_gen_model.invoke."""
    cg = _make_generator()
    cg.cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    cg._code_gen_model.invoke = AsyncMock(return_value="def foo(): pass\n")
    cg._test_gen_model.invoke = AsyncMock(return_value="# must not be reached")

    await cg.generate_code(_task("code_generation"), "code goal", "ctx", "service_component", "")

    cg._code_gen_model.invoke.assert_awaited_once()
    ctx = cg._code_gen_model.invoke.call_args.kwargs.get("context", {})
    assert "task_step" in ctx, "task_step must be passed to code_generation_task_step_prompt"
    cg._test_gen_model.invoke.assert_not_awaited()


# ID: 7eab4e8c-d619-4ff7-9cb4-85052f317f3f
async def test_test_gen_model_receives_source_content_in_goal() -> None:
    """The enriched_prompt fed as 'goal' to test_gen_prompt must contain
    whatever context the prompt_pipeline produced — which includes the source
    file content injected upstream by build_tests_action."""
    cg = _make_generator()
    cg.prompt_pipeline.process.return_value = "SOURCE: def my_func(): pass"
    cg.cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    cg._test_gen_model.invoke = AsyncMock(return_value="def test_x():\n    assert True\n")

    await cg.generate_code(_task("test_generation"), "goal", "ctx", "test_file", "")

    ctx = cg._test_gen_model.invoke.call_args.kwargs.get("context", {})
    assert "SOURCE: def my_func(): pass" in ctx["goal"]


# ID: 55f7b4a5-9dd7-4350-a221-df58356bcb52
def test_code_generator_loads_both_prompt_models() -> None:
    """CodeGenerator.__init__ must load both _code_gen_model and _test_gen_model
    so the routing branch never hits an AttributeError at call time."""
    cg = _make_generator()
    assert hasattr(cg, "_code_gen_model"), "_code_gen_model must be loaded at init"
    assert hasattr(cg, "_test_gen_model"), "_test_gen_model must be loaded at init"
    assert cg._code_gen_model is not None
    assert cg._test_gen_model is not None
