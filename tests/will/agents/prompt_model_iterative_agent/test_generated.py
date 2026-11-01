from __future__ import annotations

from will.agents.prompt_model_iterative_agent import GenerationFailedError


# ID: 519bf7fe-f3e9-41c4-9641-66859ab63cfd
def test_GenerationFailedError():
    step_ref = "step-42"
    attempts = 3
    violations = ["missing docstring", "line too long"]
    reason = "budget_exhausted"

    error = GenerationFailedError(step_ref, attempts, violations, reason)

    assert error.step_ref == step_ref
    assert error.attempts == attempts
    assert error.violations == violations
    assert error.reason == reason
    assert isinstance(error, Exception)
    assert str(error) == (
        f"Generation failed for {step_ref!r} after {attempts} attempt(s): {reason}"
    )


from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.prompt_model_iterative_agent import PromptModelIterativeAgent


@pytest.mark.asyncio
# ID: 2c399879-daf6-4eb4-9113-5a9396abb3bf
async def test_PromptModelIterativeAgent():
    agent = PromptModelIterativeAgent()

    code_body = "def foo():\n    return 1"
    fence = "`" * 3
    raw_response = fence + "python\n" + code_body + "\n" + fence

    mock_model = MagicMock()
    mock_model.manifest = MagicMock()
    mock_model.manifest.role = "codegen"
    mock_model.invoke = AsyncMock(return_value=raw_response)

    mock_cognitive = MagicMock()
    mock_cognitive.aget_client_for_role = AsyncMock(return_value=MagicMock())

    acceptance_result = MagicMock()
    acceptance_result.accepted = True
    acceptance_result.violation_summary = ""
    acceptance_result.violations = []

    mock_acceptance = MagicMock()
    mock_acceptance.evaluate = AsyncMock(return_value=acceptance_result)

    context = {"symbol_code": "def foo(): ..."}

    with (
        patch(
            "will.agents.prompt_model_iterative_agent.PromptModel.load",
            return_value=mock_model,
        ),
        patch(
            "will.agents.prompt_model_iterative_agent.load_generation_budget",
        ) as mock_budget_loader,
    ):
        budget = MagicMock()
        budget.max_iterations = 3
        budget.wall_clock_cap_secs = 60
        budget_loader_instance = MagicMock()
        budget_loader_instance.for_task_type = MagicMock(return_value=budget)
        mock_budget_loader.return_value = budget_loader_instance

        result = await agent.generate(
            prompt_name="context_aware_test_gen",
            repair_prompt_name="context_aware_test_gen_repair",
            context=context,
            target_path="tests/test_foo.py",
            acceptance=mock_acceptance,
            cognitive_service=mock_cognitive,
            step_ref="generate",
            task_type="test_generation",
        )

    assert "def foo()" in result
    assert "return 1" in result
    mock_acceptance.evaluate.assert_awaited_once()
