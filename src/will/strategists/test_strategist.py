# src/will/strategists/test_strategist.py

"""
Test Strategist - Decides test generation strategy.

Constitutional Alignment:
- Phase: RUNTIME (Deterministic decision-making)
- Authority: POLICY (Applies architectural layout rules)
- Tracing: Mandatory DecisionTracer integration
"""

from __future__ import annotations

import time

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 053f19cb-2b5b-494f-99d3-d83722d0cb26
class TestStrategist(Component):
    """
    Decides which test generation strategy to use.

    Strategy Types:
    - integration_tests: Standard for DB models, requires fixtures.
    - unit_tests: Standard for pure functions, uses mocks.
    - async_tests: Specialized for async/await concurrency.
    - integration_tests_no_introspection: Pivot for Mapped/ClassVar errors.
    """

    def __init__(self):
        self.tracer = DecisionTracer()

    @property
    # ID: b4d099d9-b659-45ea-a85f-58546defce51
    def phase(self) -> ComponentPhase:
        return ComponentPhase.RUNTIME

    # ID: 9478870b-9733-461d-be61-761ac43042a4
    async def execute(
        self,
        file_type: str,
        complexity: str = "medium",
        failure_pattern: str | None = None,
        pattern_count: int = 0,
        **kwargs,
    ) -> ComponentResult:
        """
        Decide test generation strategy with adaptive pivot logic.
        """
        start_time = time.time()
        try:
            # 1. Base Selection
            strategy, approach, constraints, requirements = self._select_base_strategy(
                file_type, complexity
            )

            # 2. Record Initial Decision
            self.tracer.record(
                agent="TestStrategist",
                decision_type="strategy_selection",
                rationale=f"Baseline for file_type '{file_type}'",
                chosen_action=strategy,
                context={"file_type": file_type, "complexity": complexity},
            )

            # 3. Adaptive Pivot logic
            if failure_pattern and pattern_count >= 2:
                prev_strategy = strategy
                strategy, approach, constraints = self._adjust_for_failures(
                    strategy, approach, constraints, failure_pattern, pattern_count
                )

                if strategy != prev_strategy:
                    self.tracer.record(
                        agent="TestStrategist",
                        decision_type="strategy_pivot",
                        rationale=f"Failure pattern '{failure_pattern}' occurred {pattern_count}x",
                        chosen_action=strategy,
                        context={"pattern": failure_pattern, "count": pattern_count},
                        confidence=0.9,
                    )

            confidence = self._calculate_confidence(
                file_type, complexity, pattern_count
            )

            duration = time.time() - start_time
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "strategy": strategy,
                    "approach": approach,
                    "constraints": constraints,
                    "requirements": requirements,
                },
                phase=self.phase,
                confidence=confidence,
                next_suggested="test_generator",
                duration_sec=duration,
                metadata={
                    "file_type": file_type,
                    "complexity": complexity,
                    "failure_pattern": failure_pattern,
                    "pattern_count": pattern_count,
                    "pivoted": bool(failure_pattern),
                },
            )
        except Exception as e:
            logger.error("TestStrategist failed: %s", e, exc_info=True)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": str(e)},
                phase=self.phase,
                confidence=0.0,
                duration_sec=time.time() - start_time,
            )

    def _select_base_strategy(
        self, file_type: str, complexity: str
    ) -> tuple[str, str, list[str], list[str]]:
        """Select base strategy based on file type."""
        if file_type == "sqlalchemy_model":
            return (
                "integration_tests",
                "Integration tests with database fixtures",
                [
                    "Do NOT use isinstance() on SQLAlchemy type annotations",
                    "Do NOT import JSONB from sqlalchemy (use dialects.postgresql)",
                ],
                [
                    "Use database fixtures from conftest.py",
                    "Test relationship loading",
                ],
            )

        if file_type == "async_module":
            return (
                "async_tests",
                "Async tests with pytest-asyncio",
                ["Do NOT use synchronous test functions"],
                ["Use async/await syntax", "Use @pytest.mark.asyncio"],
            )

        return (
            "unit_tests",
            "Unit tests with mocked dependencies",
            ["Do NOT test implementation details"],
            ["Test happy path", "Mock external dependencies"],
        )

    def _adjust_for_failures(
        self,
        strategy: str,
        approach: str,
        constraints: list[str],
        failure_pattern: str,
        pattern_count: int,
    ) -> tuple[str, str, list[str]]:
        """
        Pivots the strategy ID to break failure loops.
        """
        # CASE: Introspection Failures
        if (
            failure_pattern == "type_introspection" or failure_pattern == "unknown"
        ) and pattern_count >= 3:
            return (
                "integration_tests_no_introspection",
                "Integration tests (Introspection Disabled)",
                [
                    *constraints,
                    "CRITICAL: Do NOT use isinstance() on any object",
                    "CRITICAL: Assert on primitive values (strings, ints) only",
                ],
            )

        # CASE: Environment/Import Errors
        if "invalid_import" in failure_pattern:
            constraints.append(
                "CRITICAL: Explicitly check 'shared.' and 'body.' imports"
            )
            return (f"{strategy}_import_fixed", approach, constraints)

        # CASE: Loop Guard
        if pattern_count >= 5:
            return (
                "minimalist_tests",
                "Minimalist validation (High Failure Recovery)",
                [*constraints, "CRITICAL: Strip all complex decorators and markers"],
            )

        return (strategy, approach, constraints)

    def _calculate_confidence(
        self, file_type: str, complexity: str, pattern_count: int
    ) -> float:
        """Calculate confidence based on stability."""
        confidence_map = {
            "sqlalchemy_model": 0.9,
            "async_module": 0.85,
            "function_module": 0.8,
            "class_module": 0.8,
            "mixed_module": 0.6,
        }
        base_confidence = confidence_map.get(file_type, 0.5)

        if complexity == "high":
            base_confidence *= 0.8

        if pattern_count > 0:
            base_confidence -= 0.1 * pattern_count

        return max(0.1, min(1.0, base_confidence))
