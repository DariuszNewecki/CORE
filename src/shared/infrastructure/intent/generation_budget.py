# src/shared/infrastructure/intent/generation_budget.py
"""
Loader for .intent/enforcement/config/generation_budget.yaml (ADR-135 D4).

Governs iteration caps and wall-clock limits for IterativeCoderAgent and the
iterative loop inside build.test_for_symbol. Follows the operational_config.py
pattern: frozen dataclasses, never raises, falls back to governed defaults when
the YAML is missing or malformed.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

_CONFIG_PATH = "enforcement/config/generation_budget.yaml"

_DEFAULT_MAX_ITERATIONS = 3
_DEFAULT_WALL_CLOCK_CAP_SECS = 600


@dataclass(frozen=True)
# ID: dccb38fb-1fdb-4793-93bc-0aef0f14c7af
class TaskBudget:
    """Iteration budget for a single task_type."""

    max_iterations: int
    wall_clock_cap_secs: int


@dataclass(frozen=True)
# ID: 4b906cfa-648b-481c-a88f-acb6d4301868
class GenerationBudget:
    """Full budget table loaded from generation_budget.yaml."""

    _budgets: dict[str, TaskBudget]

    # ID: 03a97f5d-8d14-4b0e-bc74-d6c79491dda3
    def for_task_type(self, task_type: str) -> TaskBudget:
        """Return the budget for task_type, falling back to 'default'."""
        return self._budgets.get(
            task_type,
            self._budgets.get(
                "default",
                TaskBudget(_DEFAULT_MAX_ITERATIONS, _DEFAULT_WALL_CLOCK_CAP_SECS),
            ),
        )


def _parse_budget(raw: Any) -> TaskBudget:
    if not isinstance(raw, dict):
        return TaskBudget(_DEFAULT_MAX_ITERATIONS, _DEFAULT_WALL_CLOCK_CAP_SECS)
    try:
        return TaskBudget(
            max_iterations=int(raw.get("max_iterations", _DEFAULT_MAX_ITERATIONS)),
            wall_clock_cap_secs=int(
                raw.get("wall_clock_cap_secs", _DEFAULT_WALL_CLOCK_CAP_SECS)
            ),
        )
    except (TypeError, ValueError):
        return TaskBudget(_DEFAULT_MAX_ITERATIONS, _DEFAULT_WALL_CLOCK_CAP_SECS)


@functools.lru_cache(maxsize=1)
# ID: 591a67fd-0741-4c0e-bd69-592fd630d1cc
def load_generation_budget() -> GenerationBudget:
    """
    Load generation_budget.yaml via IntentRepository.

    Never raises. Falls back to hardcoded defaults on any failure.
    """
    try:
        import yaml

        from shared.infrastructure.intent.intent_repository import get_intent_repository

        repo = get_intent_repository()
        raw = yaml.safe_load(repo.load_text(_CONFIG_PATH))
        if not isinstance(raw, dict):
            logger.warning(
                "generation_budget: unexpected top-level type %s — using defaults",
                type(raw).__name__,
            )
            return _default_budget()

        budgets_raw = raw.get("budgets", {})
        if not isinstance(budgets_raw, dict):
            logger.warning("generation_budget: 'budgets' key missing or not a dict")
            return _default_budget()

        budgets = {k: _parse_budget(v) for k, v in budgets_raw.items()}
        return GenerationBudget(_budgets=budgets)

    except Exception as exc:
        logger.warning("generation_budget: failed to load — using defaults (%s)", exc)
        return _default_budget()


def _default_budget() -> GenerationBudget:
    return GenerationBudget(
        _budgets={
            "test_generation": TaskBudget(5, 600),
            "code_modification": TaskBudget(3, 600),
            "code_generation": TaskBudget(3, 600),
            "default": TaskBudget(3, 600),
        }
    )
