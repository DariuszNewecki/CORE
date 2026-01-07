# src/body/evaluators/failure_evaluator.py

"""
Failure Evaluator - Analyzes test failure patterns for strategy adaptation.

Constitutional Alignment:
- Phase: AUDIT (Evaluates test execution evidence)
- Authority: POLICY (Implements failure classification logic)
- Tracing: Mandatory DecisionTracer integration
"""

from __future__ import annotations

import time
from collections import Counter

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 68e33e74-f15f-4f97-b58a-7df6aa0fa7a7
class FailureEvaluator(Component):
    """
    Analyzes test failure strings to identify recurring patterns.
    Enables the 'Will' layer to adapt strategies based on observed 'Body' failures.

    Pattern Classification:
    - type_introspection: Mapped/ClassVar/isinstance issues.
    - invalid_import: ModuleNotFoundError or missing imports.
    - logic_error_missing_name: NameError (often indicates missing mock or local).
    - mock_failure: AttributeErrors related to MagicMock/patch.
    - assertion_failure: Standard value mismatches.
    """

    def __init__(self):
        self.tracer = DecisionTracer()

    @property
    # ID: e78245a6-eaa8-4d77-baf5-c68100cb84be
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: 31ed733a-6ed4-429a-bb5d-f1612a589104
    async def execute(
        self, error: str, pattern_history: list[str] | None = None, **kwargs
    ) -> ComponentResult:
        """
        Evaluates a single failure and recommends an adaptive action.

        Args:
            error: The raw stderr/stdout from the test run.
            pattern_history: List of previously identified patterns for this session.

        Returns:
            ComponentResult containing the identified pattern and a pivot recommendation.
        """
        start_time = time.time()
        pattern_history = pattern_history or []

        # 1. Pattern Extraction (Audit logic)
        pattern = self._extract_pattern(error)
        pattern_history.append(pattern)

        pattern_counts = Counter(pattern_history)
        occurrences = pattern_counts[pattern]

        # 2. Strategy Mapping (Decision logic)
        # Recommendation escalates based on frequency
        if occurrences >= 3:
            recommendation = "switch_strategy"
            should_switch = True
            confidence = 0.95
            next_suggested = "test_strategist"
        elif occurrences == 2:
            recommendation = "adjust_prompt"
            should_switch = False
            confidence = 0.7
            next_suggested = "test_generator"
        else:
            recommendation = "retry"
            should_switch = False
            confidence = 0.5
            next_suggested = "test_generator"

        # 3. Mandatory Tracing (Constitutional Requirement)
        self.tracer.record(
            agent="FailureEvaluator",
            decision_type="failure_analysis",
            rationale=f"Observed pattern '{pattern}' (Count: {occurrences})",
            chosen_action=recommendation,
            context={
                "pattern": pattern,
                "occurrences": occurrences,
                "raw_error_preview": error[:100],
            },
            confidence=confidence,
        )

        duration = time.time() - start_time
        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={
                "pattern": pattern,
                "occurrences": occurrences,
                "should_switch": should_switch,
                "recommendation": recommendation,
            },
            phase=self.phase,
            confidence=confidence,
            next_suggested=next_suggested,
            duration_sec=duration,
            metadata={
                "pattern_history": pattern_history,
                "summary": self.get_pattern_summary(pattern_history),
            },
        )

    def _extract_pattern(self, error: str) -> str:
        """
        Extract failure pattern using order-insensitive keyword matching.
        """
        err_lower = error.lower()

        # 1. Environment / Setup Errors (High priority for Adaptive Loop)
        if "modulenotfounderror" in err_lower or "importerror" in err_lower:
            return "invalid_import"

        if "nameerror" in err_lower:
            return "logic_error_missing_name"

        # 2. Type System / Introspection Errors (SQLAlchemy / Mapped)
        if "isinstance" in err_lower and (
            "classvar" in err_lower or "mapped" in err_lower or "typing" in err_lower
        ):
            return "type_introspection"

        # 3. Mocking and Attribute Failures
        if "attributeerror" in err_lower:
            if "mock" in err_lower or "patch" in err_lower:
                return "mock_placement"
            if "datetime" in err_lower:
                return "mock_datetime"
            return "attribute_error_generic"

        # 4. Data/Comparison Failures
        if "assertionerror" in err_lower:
            if "==" in err_lower:
                if "object at 0x" in err_lower:
                    return "object_identity_comparison"
                return "assertion_comparison"
            return "assertion_error"

        # 5. DB / Infrastructure Specifics
        if "sqlalchemy" in err_lower:
            if "session" in err_lower:
                return "sqlalchemy_session"
            if "relationship" in err_lower:
                return "sqlalchemy_relationship"
            return "sqlalchemy_generic"

        # 6. Runtime Constraints
        if "timeout" in err_lower or "timed out" in err_lower:
            return "test_timeout"

        if "fixture" in err_lower and (
            "not found" in err_lower or "error" in err_lower
        ):
            return "fixture_error"

        return "unknown"

    # ID: b2e43a2a-8c95-4963-a55b-8f75dbf7dbe6
    def get_pattern_summary(self, pattern_history: list[str]) -> dict:
        """
        Generates aggregate statistics for the current generation session.
        Used for the final 'Patterns Learned' CLI output.
        """
        if not pattern_history:
            return {"total": 0, "unique": 0, "most_common": None, "patterns": {}}

        counts = Counter(pattern_history)
        most_common_data = counts.most_common(1)

        return {
            "total": len(pattern_history),
            "unique": len(counts),
            "most_common": most_common_data[0][0] if most_common_data else None,
            "patterns": dict(counts),
        }
