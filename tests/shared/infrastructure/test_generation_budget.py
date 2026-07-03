# tests/shared/infrastructure/test_generation_budget.py
"""Tests for GenerationBudget loader (ADR-135 D4)."""

from __future__ import annotations

from unittest.mock import patch

from shared.infrastructure.intent.generation_budget import (
    GenerationBudget,
    TaskBudget,
    _default_budget,
    load_generation_budget,
)


def test_default_budget_has_expected_task_types():
    budget = _default_budget()
    assert budget.for_task_type("test_generation").max_iterations == 5
    assert budget.for_task_type("code_modification").max_iterations == 3
    assert budget.for_task_type("default").max_iterations == 3


def test_for_task_type_falls_back_to_default():
    budget = _default_budget()
    result = budget.for_task_type("completely_unknown_type")
    assert result.max_iterations == 3


def test_for_task_type_returns_exact_match():
    budget = _default_budget()
    result = budget.for_task_type("test_generation")
    assert result.max_iterations == 5
    assert result.wall_clock_cap_secs == 600


def test_task_budget_frozen():
    tb = TaskBudget(max_iterations=5, wall_clock_cap_secs=600)
    assert tb.max_iterations == 5
    assert tb.wall_clock_cap_secs == 600


def test_load_generation_budget_returns_generation_budget():
    import yaml

    # Clear any cached result first
    load_generation_budget.cache_clear()
    with patch(
        "shared.infrastructure.intent.generation_budget.get_intent_repository"
    ) as mock_repo:
        mock_repo.return_value.load_text.return_value = yaml.dump({
            "budgets": {
                "test_generation": {"max_iterations": 7, "wall_clock_cap_secs": 300},
                "default": {"max_iterations": 2, "wall_clock_cap_secs": 120},
            }
        })
        result = load_generation_budget()

    assert isinstance(result, GenerationBudget)
    assert result.for_task_type("test_generation").max_iterations == 7
    assert result.for_task_type("default").max_iterations == 2
    load_generation_budget.cache_clear()


def test_load_generation_budget_falls_back_on_error():
    load_generation_budget.cache_clear()
    with patch(
        "shared.infrastructure.intent.generation_budget.get_intent_repository",
        side_effect=RuntimeError("repo unavailable"),
    ):
        result = load_generation_budget()

    assert isinstance(result, GenerationBudget)
    assert result.for_task_type("test_generation").max_iterations == 5
    load_generation_budget.cache_clear()
