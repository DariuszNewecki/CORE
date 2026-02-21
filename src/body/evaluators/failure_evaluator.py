# src/body/evaluators/failure_evaluator.py
# ID: 68e33e74-f15f-4f97-b58a-7df6aa0fa7a7
"""Failure Evaluator - Analyzes test failure patterns for strategy adaptation.

PURIFIED (V2.3.0)
- Removed Will-layer 'DecisionTracer' to satisfy layer separation.
- Pivot recommendations and patterns returned in data/metadata for the Strategist.
"""

from __future__ import annotations

import time
from collections import Counter

# from shared.component_primitive import Component, ComponentPhase, ComponentResult
from body.evaluators.base_evaluator import BaseEvaluator
from shared.component_primitive import ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: ef17c136-eb2b-4756-8eef-635c7ddc9546
class FailureEvaluator(BaseEvaluator):
    """Analyze test failure strings to identify recurring patterns.

    Enables the Will layer to adapt strategies based on observed Body failures.
    """

    # ID: 31ed733a-6ed4-429a-bb5d-f1612a589104
    async def execute(
        self,
        error: str,
        pattern_history: list[str] | None = None,
        **kwargs,
    ) -> ComponentResult:
        """Evaluate a single failure and recommend an adaptive action."""
        start_time = time.time()
        history = list(pattern_history or [])

        # 1) Pattern extraction
        pattern = self._extract_pattern(error)
        history.append(pattern)

        pattern_counts = Counter(history)
        occurrences = pattern_counts[pattern]

        # 2) Strategy mapping
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

        duration = time.time() - start_time

        # 3) Metadata carrier: replaces direct tracing
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
                "pattern_history": history,
                "rationale": (
                    f"Observed pattern '{pattern}' (Count: {occurrences}). "
                    f"Recommending: {recommendation}"
                ),
                "summary": self.get_pattern_summary(history),
            },
        )

    def _extract_pattern(self, error: str) -> str:
        err_lower = error.lower()

        if "modulenotfounderror" in err_lower or "importerror" in err_lower:
            return "invalid_import"
        if "nameerror" in err_lower:
            return "logic_error_missing_name"
        if "isinstance" in err_lower and (
            "classvar" in err_lower or "mapped" in err_lower
        ):
            return "type_introspection"
        if "attributeerror" in err_lower:
            return (
                "mock_placement" if "mock" in err_lower else "attribute_error_generic"
            )
        if "assertionerror" in err_lower:
            return (
                "object_identity_comparison"
                if "0x" in err_lower
                else "assertion_comparison"
            )
        if "sqlalchemy" in err_lower:
            return (
                "sqlalchemy_session" if "session" in err_lower else "sqlalchemy_generic"
            )
        if "timeout" in err_lower:
            return "test_timeout"
        if "fixture" in err_lower:
            return "fixture_error"

        return "unknown"

    # ID: beb602c2-ebd9-4f2a-bc53-8009101556eb
    def get_pattern_summary(self, pattern_history: list[str]) -> dict:
        if not pattern_history:
            return {"total": 0, "unique": 0, "patterns": {}}

        counts = Counter(pattern_history)
        most_common = counts.most_common(1)[0][0] if counts else None

        return {
            "total": len(pattern_history),
            "unique": len(counts),
            "most_common": most_common,
            "patterns": dict(counts),
        }
