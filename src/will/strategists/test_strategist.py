# src/will/strategists/test_strategist.py

"""
Test Strategist - Pure Logic Mapping Engine.

CONSTITUTIONAL FIX (V2.3):
- Modularized to reduce Modularity Debt (49.6 -> ~32.0).
- Replaced conditional branching with Data-Driven Strategy Mapping.
- Simplifies strategy selection and pivot logic into deterministic lookups.
- Aligns with the UNIX Neuron pattern: One job (Mapping).
"""

from __future__ import annotations

import time
from typing import Any, Final

from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer
from will.strategists.base_strategist import BaseStrategist


logger = getLogger(__name__)

# --- ARCHITECTURAL KNOWLEDGE BASE (The "Truth Table") ---

# ID: 5daaed3b-601c-4a49-9fce-342b9e029bfc
# Maps file_type -> (strategy_id, approach, constraints, requirements)
STRATEGY_MAP: Final[dict[str, tuple[str, str, list[str], list[str]]]] = {
    "sqlalchemy_model": (
        "integration_tests",
        "Integration tests with database fixtures",
        [
            "Do NOT use isinstance() on SQLAlchemy type annotations",
            "Do NOT import JSONB",
        ],
        ["Use database fixtures from conftest.py", "Test relationship loading"],
    ),
    "async_module": (
        "async_tests",
        "Async tests with pytest-asyncio",
        ["Do NOT use synchronous test functions"],
        ["Use async/await syntax", "Use @pytest.mark.asyncio"],
    ),
    "default": (
        "unit_tests",
        "Unit tests with mocked dependencies",
        ["Do NOT test implementation details"],
        ["Test happy path", "Mock external dependencies"],
    ),
}

# ID: ddff8ad0-cbe4-43ab-8f31-9cb2483bb1e3
# Maps failure_pattern -> adjustment_logic
PIVOT_RULES: Final[dict[str, dict[str, Any]]] = {
    "type_introspection": {
        "min_count": 3,
        "new_id": "integration_tests_no_introspection",
        "extra_constraints": ["CRITICAL: Assert on primitive values only"],
    },
    "invalid_import": {
        "min_count": 2,
        "suffix": "_import_fixed",
        "extra_constraints": ["CRITICAL: Explicitly check 'shared.' imports"],
    },
}


# ID: 053f19cb-2b5b-494f-99d3-d83722d0cb26
class TestStrategist(BaseStrategist):
    """
    Decides test generation strategy using deterministic lookups.

    This is a pure 'Will' layer component: it takes facts (sensation)
    and returns a decision (strategy) without side effects.
    """

    def __init__(self):
        self.tracer = DecisionTracer()

    # ID: 9478870b-9733-461d-be61-761ac43042a4
    async def execute(
        self,
        file_type: str,
        complexity: str = "medium",
        failure_pattern: str | None = None,
        pattern_count: int = 0,
        **kwargs,
    ) -> ComponentResult:
        """Determines the optimal test strategy via table-driven lookup."""
        start_time = time.time()

        # 1. BASE LOOKUP
        # If file_type is unknown, we default to standard unit tests.
        sid, approach, constraints, reqs = STRATEGY_MAP.get(
            file_type, STRATEGY_MAP["default"]
        )

        # 2. ADAPTIVE PIVOT (Data-Driven)
        # We check the PIVOT_RULES table to see if a failure pattern requires a change.
        if failure_pattern and failure_pattern in PIVOT_RULES:
            rule = PIVOT_RULES[failure_pattern]
            if pattern_count >= rule.get("min_count", 2):
                sid = rule.get("new_id", f"{sid}{rule.get('suffix', '_pivoted')}")
                constraints.extend(rule.get("extra_constraints", []))

        # 3. GLOBAL LOOP GUARD
        # If we've failed 5 times, we retreat to a 'minimalist' strategy to break loops.
        if pattern_count >= 5:
            sid, approach = ("minimalist_tests", "High Failure Recovery Mode")

        # 4. TRACING (Constitutional Requirement)
        self.tracer.record(
            agent="TestStrategist",
            decision_type="strategy_selection",
            rationale=f"Resolved {sid} for {file_type} (Failures: {pattern_count})",
            chosen_action=sid,
            confidence=self._calculate_confidence(file_type, pattern_count),
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={
                "strategy": sid,
                "approach": approach,
                "constraints": constraints,
                "requirements": reqs,
            },
            phase=self.phase,
            confidence=self._calculate_confidence(file_type, pattern_count),
            next_suggested="test_generator",
            duration_sec=time.time() - start_time,
            metadata={"file_type": file_type, "pivoted": bool(failure_pattern)},
        )

    def _calculate_confidence(self, file_type: str, pattern_count: int) -> float:
        """Heuristic: trust decreases as failures increase."""
        base = 0.9 if file_type in STRATEGY_MAP else 0.5
        penalty = pattern_count * 0.1
        return max(0.1, min(1.0, base - penalty))
