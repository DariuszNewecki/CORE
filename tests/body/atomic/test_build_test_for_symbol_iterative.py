# tests/body/atomic/test_build_test_for_symbol_iterative.py
"""
Tests for build.test_for_symbol iterative mode (ADR-135 D1/D3).

Verifies that with generation_mode='iterative' the action retries on
IntentGuard violations and succeeds when a later attempt passes validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.governance_token import authorize_execution


@pytest.fixture
def mock_core_context(tmp_path):
    ctx = MagicMock()
    ctx.git_service.repo_path = tmp_path
    ctx.cognitive_service = None
    ctx.file_handler = MagicMock()
    ctx.file_handler.write = MagicMock()
    mock_registry = AsyncMock()
    mock_cog = AsyncMock()
    mock_client = AsyncMock()
    mock_cog.aget_client_for_role = AsyncMock(return_value=mock_client)
    mock_registry.get_cognitive_service = AsyncMock(return_value=mock_cog)
    ctx.registry = mock_registry
    return ctx


@pytest.fixture
def source_setup(tmp_path):
    src_dir = tmp_path / "src" / "mypkg"
    src_dir.mkdir(parents=True)
    src_file = src_dir / "service.py"
    src_file.write_text("def do_work(x):\n    return x * 2\n")
    return "src/mypkg/service.py"


def _good_response():
    return "```python\nfrom __future__ import annotations\n\ndef test_do_work():\n    assert do_work(2) == 4\n```"


def _bad_response():
    return "```python\nfrom __future__ import annotations\n\ndef test_do_work():\n    pass\n```"


def _make_violation(rule_name="code.tests.no_placeholder_test_body"):
    v = MagicMock()
    v.rule_name = rule_name
    v.message = "No assertion"
    v.severity = "error"
    return v


@pytest.mark.asyncio
async def test_iterative_succeeds_on_second_attempt(mock_core_context, source_setup):
    """First attempt fails IntentGuard; second attempt passes."""
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    fail_validation = MagicMock()
    fail_validation.is_valid = False
    fail_validation.violations = [_make_violation()]

    pass_validation = MagicMock()
    pass_validation.is_valid = True
    pass_validation.violations = []

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
            "body.atomic.build_test_for_symbol_action.PromptModel.load",
            side_effect=lambda name: repair_model if name == "context_aware_test_gen_repair" else initial_model,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.load_generation_budget",
        ) as mock_budget,
        authorize_execution("build.test_for_symbol"),
    ):
        from shared.infrastructure.intent.generation_budget import (
            TaskBudget,
        )
        mock_budget.return_value.for_task_type.return_value = TaskBudget(5, 600)

        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            signature="def do_work(x)",
            core_context=mock_core_context,
            write=False,
            generation_mode="iterative",
        )

    assert result.ok, result.data
    assert result.data["attempts"] == 2
    assert result.data["generation_mode"] == "iterative"
    repair_model.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_iterative_fails_after_cap_exhausted(mock_core_context, source_setup):
    """All attempts fail IntentGuard — returns not ok."""
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    fail_validation = MagicMock()
    fail_validation.is_valid = False
    fail_validation.violations = [_make_violation()]

    model = MagicMock()
    model.manifest.role = "Coder"
    model.invoke = AsyncMock(return_value=_bad_response())

    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=fail_validation)

    with (
        patch(
            "body.atomic.build_test_for_symbol_action.PromptModel.load",
            return_value=model,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.load_generation_budget",
        ) as mock_budget,
        authorize_execution("build.test_for_symbol"),
    ):
        from shared.infrastructure.intent.generation_budget import TaskBudget
        mock_budget.return_value.for_task_type.return_value = TaskBudget(3, 600)

        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            signature="def do_work(x)",
            core_context=mock_core_context,
            write=False,
            generation_mode="iterative",
        )

    assert not result.ok
    assert result.data["error"] == "intent_guard_violations"
    assert result.data["attempts"] == 3
    assert intent_guard.validate_generated_code.call_count == 3


@pytest.mark.asyncio
async def test_single_shot_does_not_retry_on_violation(mock_core_context, source_setup):
    """single_shot mode returns immediately on first violation (no retry)."""
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    fail_validation = MagicMock()
    fail_validation.is_valid = False
    fail_validation.violations = [_make_violation()]

    model = MagicMock()
    model.manifest.role = "Coder"
    model.invoke = AsyncMock(return_value=_bad_response())

    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=fail_validation)

    with (
        patch(
            "body.atomic.build_test_for_symbol_action.PromptModel.load",
            return_value=model,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        authorize_execution("build.test_for_symbol"),
    ):
        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            signature="def do_work(x)",
            core_context=mock_core_context,
            write=False,
            generation_mode="single_shot",
        )

    assert not result.ok
    assert intent_guard.validate_generated_code.call_count == 1
