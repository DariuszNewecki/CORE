# src/body/evaluators/clarity_evaluator.py
# ID: 7fcecf85-269a-419c-81a3-30b1fea807b8

"""
Clarity Evaluator - Measures mathematical improvement in code structure.
CONSTITUTIONAL PROMOTION: Fulfilled BaseEvaluator contract.
"""

from __future__ import annotations

import time

from radon.visitors import ComplexityVisitor

from shared.component_primitive import ComponentPhase, ComponentResult
from shared.logger import getLogger

from .base_evaluator import BaseEvaluator


logger = getLogger(__name__)


# ID: d4aa43cb-e62b-4a50-b34e-9aa12144a561
class ClarityEvaluator(BaseEvaluator):
    """Evaluate refactoring results by comparing Cyclomatic Complexity (CC)."""

    @property
    # ID: 04c638f6-5c8b-4ea4-a80e-39b607fec1e2
    def component_id(self) -> str:
        return "clarity_evaluator"

    @property
    # ID: 85122bba-ab4f-42bc-b320-7a658c8444ef
    def phase(self) -> str:
        return ComponentPhase.AUDIT.value

    # ID: c35226bd-1d63-46fc-9ceb-f3c5a1d63208
    async def evaluate(
        self, original_code: str, new_code: str, **kwargs
    ) -> ComponentResult:
        """
        Calculates the improvement ratio between two versions of code.
        Implementation of the abstract 'evaluate' method.
        """
        start_time = time.time()

        try:
            # 1. Sensation: Analyze original
            orig_visitor = ComplexityVisitor.from_code(original_code)
            orig_cc = sum(block.complexity for block in orig_visitor.blocks)

            # 2. Sensation: Analyze proposed
            new_visitor = ComplexityVisitor.from_code(new_code)
            new_cc = sum(block.complexity for block in new_visitor.blocks)

            # 3. Analysis: Calculate metrics
            improvement = (orig_cc - new_cc) / orig_cc if orig_cc > 0 else 0.0
            is_better = new_cc < orig_cc  # Must be strictly better

            duration = time.time() - start_time

            return await self._create_result(
                ok=True,
                data={
                    "original_cc": orig_cc,
                    "new_cc": new_cc,
                    "improvement_ratio": round(improvement, 4),
                    "is_better": is_better,
                },
                confidence=1.0,
                duration=duration,
                rationale=(
                    f"Quality Assessment: Original CC {orig_cc} -> New CC {new_cc}. "
                    f"Improved: {is_better}"
                ),
            )

        except Exception as e:
            logger.error("ClarityEvaluator: analysis failed: %s", e, exc_info=True)
            return await self._create_result(
                ok=False,
                data={"error": f"Radon analysis failed: {e!s}"},
                confidence=0.0,
                duration=time.time() - start_time,
                rationale="Failed to perform radon complexity analysis.",
            )
