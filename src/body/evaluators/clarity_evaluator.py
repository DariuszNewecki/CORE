# src/body/evaluators/clarity_evaluator.py
# ID: 7fcecf85-269a-419c-81a3-30b1fea807b8

"""
Clarity Evaluator - Measures mathematical improvement in code structure.

HEALED (V2.7.0):
- Inherits from BaseEvaluator for strict contract compliance.
- Explicit Decision Tracing: Records complexity improvements for the AI to learn.
"""

from __future__ import annotations

import time

from radon.visitors import ComplexityVisitor

from shared.component_primitive import ComponentResult
from shared.logger import getLogger

from .base_evaluator import BaseEvaluator


logger = getLogger(__name__)


# ID: clarity-judge-v2
# ID: d4aa43cb-e62b-4a50-b34e-9aa12144a561
class ClarityEvaluator(BaseEvaluator):
    """
    Evaluates refactoring results by comparing Cyclomatic Complexity (CC).
    """

    # ID: c35226bd-1d63-46fc-9ceb-f3c5a1d63208
    async def execute(
        self, original_code: str, new_code: str, **kwargs
    ) -> ComponentResult:
        """
        Calculates improvement ratio between two versions of code.
        """
        start_time = time.time()

        try:
            # 1. SENSATION: Analyze Original
            orig_visitor = ComplexityVisitor.from_code(original_code)
            orig_cc = sum(block.complexity for block in orig_visitor.blocks)

            # 2. SENSATION: Analyze Proposed
            new_visitor = ComplexityVisitor.from_code(new_code)
            new_cc = sum(block.complexity for block in new_visitor.blocks)

            # 3. ANALYSIS: Calculate Metrics
            improvement = (orig_cc - new_cc) / orig_cc if orig_cc > 0 else 0
            is_better = new_cc <= orig_cc

            # 4. DECISION TRACING: Record the "Judicial Opinion"
            self.tracer.record(
                agent="ClarityEvaluator",
                decision_type="quality_assessment",
                rationale=f"Original CC: {orig_cc} | New CC: {new_cc}",
                chosen_action="PASS" if is_better else "FAIL",
                context={
                    "improvement_ratio": round(improvement, 4),
                    "is_better": is_better,
                },
                confidence=1.0,
            )

            duration = time.time() - start_time
            return await self._create_result(
                ok=True,  # The evaluation itself worked
                data={
                    "original_cc": orig_cc,
                    "new_cc": new_cc,
                    "improvement_ratio": round(improvement, 4),
                    "is_better": is_better,
                },
                confidence=1.0,
                duration=duration,
            )

        except Exception as e:
            logger.error("ClarityEvaluator: Analysis failed. %s", e)
            return await self._create_result(
                ok=False,
                data={"error": f"Radon analysis failed: {e!s}"},
                confidence=0.0,
                duration=time.time() - start_time,
            )
