# tests/body/atomic/test_build_test_for_symbol_iterative.py
"""
Tests for PromptModelIterativeAgent — Will-tier iterative generation (ADR-140 D5).

The iterative loop previously lived in body/atomic/build_test_for_symbol_action.py
(ADR-135 D1/D3). It was extracted to PromptModelIterativeAgent by ADR-140. These
tests verify the loop contract: retry on violation, succeed on repair, fail after cap.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.prompt_model_iterative_agent import (
    GenerationFailedError,
    PromptModelIterativeAgent,
)


def _good_response() -> str:
    return "```python\nfrom __future__ import annotations\n\ndef test_do_work():\n    assert do_work(2) == 4\n```"


def _bad_response() -> str:
    return "```python\nfrom __future__ import annotations\n\ndef test_do_work():\n    pass\n```"


def _make_violation(
    rule_name: str = "code.tests.no_placeholder_test_body",
) -> MagicMock:
    v = MagicMock()
    v.rule_name = rule_name
    v.message = "No assertion"
    v.severity = "error"
    return v


@pytest.fixture
def agent() -> PromptModelIterativeAgent:
    return PromptModelIterativeAgent()


@pytest.fixture
def mock_cognitive_service() -> MagicMock:
    svc = AsyncMock()
    svc.aget_client_for_role = AsyncMock(return_value=AsyncMock())
    return svc


@pytest.mark.asyncio
async def test_iterative_succeeds_on_second_attempt(
    agent: PromptModelIterativeAgent,
    mock_cognitive_service: MagicMock,
    tmp_path: Path,
) -> None:
    """First attempt fails IntentGuard; second attempt (repair) passes."""
    fail_validation = MagicMock(is_valid=False, violations=[_make_violation()])
    pass_validation = MagicMock(is_valid=True, violations=[])

    initial_model = MagicMock()
    initial_model.manifest.role = "Coder"
    initial_model.invoke = AsyncMock(return_value=_bad_response())

    repair_model = MagicMock()
    repair_model.manifest.role = "Coder"
    repair_model.invoke = AsyncMock(return_value=_good_response())

    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(
        side_effect=[fail_validation, pass_validation]
    )

    with (
        patch(
            "will.agents.prompt_model_iterative_agent.PromptModel.load",
            side_effect=lambda name: (
                repair_model
                if name == "context_aware_test_gen_repair"
                else initial_model
            ),
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.load_generation_budget",
        ) as mock_budget,
    ):
        from shared.infrastructure.intent.generation_budget import TaskBudget

        mock_budget.return_value.for_task_type.return_value = TaskBudget(5, 600)

        result = await agent.generate(
            prompt_name="context_aware_test_gen",
            repair_prompt_name="context_aware_test_gen_repair",
            context={
                "file_path": "src/x.py",
                "symbol_name": "do_work",
                "symbol_code": "def do_work(x): ...",
                "module_path": "x",
            },
            target_path="tests/x/test_generated.py",
            cognitive_service=mock_cognitive_service,
            repo_root=tmp_path,
            step_ref="generate.test_snippet",
        )

    assert "def test_do_work" in result
    repair_model.invoke.assert_called_once()
    assert intent_guard.validate_generated_code.call_count == 2


@pytest.mark.asyncio
async def test_iterative_raises_after_cap_exhausted(
    agent: PromptModelIterativeAgent,
    mock_cognitive_service: MagicMock,
    tmp_path: Path,
) -> None:
    """All attempts fail IntentGuard — raises GenerationFailedError."""
    fail_validation = MagicMock(is_valid=False, violations=[_make_violation()])

    model = MagicMock()
    model.manifest.role = "Coder"
    model.invoke = AsyncMock(return_value=_bad_response())

    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=fail_validation)

    with (
        patch(
            "will.agents.prompt_model_iterative_agent.PromptModel.load",
            return_value=model,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.load_generation_budget",
        ) as mock_budget,
    ):
        from shared.infrastructure.intent.generation_budget import TaskBudget

        mock_budget.return_value.for_task_type.return_value = TaskBudget(3, 600)

        with pytest.raises(GenerationFailedError) as exc_info:
            await agent.generate(
                prompt_name="context_aware_test_gen",
                repair_prompt_name="context_aware_test_gen_repair",
                context={
                    "file_path": "src/x.py",
                    "symbol_name": "do_work",
                    "symbol_code": "def do_work(x): ...",
                    "module_path": "x",
                },
                target_path="tests/x/test_generated.py",
                cognitive_service=mock_cognitive_service,
                repo_root=tmp_path,
                step_ref="generate.test_snippet",
            )

    assert exc_info.value.attempts == 3
    assert exc_info.value.reason == "intent_guard_violations"
    assert intent_guard.validate_generated_code.call_count == 3


@pytest.mark.asyncio
async def test_single_attempt_passes_on_first_try(
    agent: PromptModelIterativeAgent,
    mock_cognitive_service: MagicMock,
    tmp_path: Path,
) -> None:
    """Cap=1 — passes on first attempt, no repair model loaded."""
    pass_validation = MagicMock(is_valid=True, violations=[])

    model = MagicMock()
    model.manifest.role = "Coder"
    model.invoke = AsyncMock(return_value=_good_response())

    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=pass_validation)

    with (
        patch(
            "will.agents.prompt_model_iterative_agent.PromptModel.load",
            return_value=model,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.load_generation_budget",
        ) as mock_budget,
    ):
        from shared.infrastructure.intent.generation_budget import TaskBudget

        mock_budget.return_value.for_task_type.return_value = TaskBudget(1, 600)

        result = await agent.generate(
            prompt_name="context_aware_test_gen",
            repair_prompt_name="context_aware_test_gen_repair",
            context={
                "file_path": "src/x.py",
                "symbol_name": "do_work",
                "symbol_code": "def do_work(x): ...",
                "module_path": "x",
            },
            target_path="tests/x/test_generated.py",
            cognitive_service=mock_cognitive_service,
            repo_root=tmp_path,
            step_ref="generate.test_snippet",
        )

    assert "def test_do_work" in result
    assert intent_guard.validate_generated_code.call_count == 1
