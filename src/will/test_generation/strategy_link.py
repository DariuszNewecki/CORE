# src/will/test_generation/strategy_link.py

"""
StrategyNeuralLink - Manages adaptive strategy pivots.
Will Layer: Decision logic for failure recovery.
"""

from __future__ import annotations

from typing import Any

from body.evaluators.failure_evaluator import FailureEvaluator
from shared.logger import getLogger
from will.strategists.test_strategist import TestStrategist


logger = getLogger(__name__)


# ID: eebcbbd9-2878-4d92-ba25-1bff577f09f9
# ID: 74d94246-ddd7-4db9-8d80-a1eae0adf66f
class StrategyNeuralLink:
    """Orchestrates the 'Failure -> Analysis -> Pivot' logic."""

    def __init__(self, strategist: TestStrategist, evaluator: FailureEvaluator):
        self.strategist = strategist
        self.evaluator = evaluator
        self.pattern_history: list[str] = []

    # ID: 5fd6747a-1720-4e0b-a1bc-1384aa33d156
    async def determine_pivot(
        self, error_msg: str, file_type: str, complexity: str
    ) -> tuple[Any, bool, str]:
        """
        Analyzes a failure and returns a new strategy if a pivot is required.
        """
        eval_result = await self.evaluator.execute(
            error=error_msg, pattern_history=self.pattern_history
        )

        pattern = eval_result.data["pattern"]
        self.pattern_history = eval_result.metadata["pattern_history"]
        should_switch = eval_result.data.get("should_switch", False)

        if should_switch:
            logger.info(
                "🔄 Strategy Neural Link: Triggering pivot for pattern '%s'", pattern
            )
            new_strategy = await self.strategist.execute(
                file_type=file_type,
                complexity=complexity,
                failure_pattern=pattern,
                pattern_count=eval_result.data["occurrences"],
            )
            return new_strategy, True, pattern

        return None, False, pattern
