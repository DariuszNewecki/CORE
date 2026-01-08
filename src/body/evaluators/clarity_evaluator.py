# src/body/evaluators/clarity_evaluator.py

"""
Clarity Evaluator - Measures mathematical improvement in code structure.
CONSTITUTIONAL FIX: Corrected Radon API usage to sum block complexity.
"""

from __future__ import annotations

import time

from radon.visitors import ComplexityVisitor

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 7fcecf85-269a-419c-81a3-30b1fea807b8
class ClarityEvaluator(Component):
    """
    Evaluates refactoring results by comparing Cyclomatic Complexity (CC).
    Success is defined as the new code having a lower or equal CC score.
    """

    @property
    # ID: 1c695dff-cbf2-4519-9ba2-9bb2124dfff2
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: 0b107e76-7ba7-4130-89c6-898a264f72b1
    async def execute(
        self, original_code: str, new_code: str, **kwargs
    ) -> ComponentResult:
        """
        Calculates improvement ratio between two versions of code.

        Args:
            original_code: The source code before refactoring.
            new_code: The source code after refactoring.

        Returns:
            ComponentResult containing CC metrics and 'is_better' flag.
        """
        start_time = time.time()

        try:
            # 1. ANALYZE ORIGINAL
            # ComplexityVisitor.from_code(code) is the correct Radon entry point
            orig_visitor = ComplexityVisitor.from_code(original_code)
            # Sum complexity of all blocks (functions, classes, methods) to get total file debt
            orig_cc = sum(block.complexity for block in orig_visitor.blocks)

            # 2. ANALYZE PROPOSED
            new_visitor = ComplexityVisitor.from_code(new_code)
            new_cc = sum(block.complexity for block in new_visitor.blocks)

            # 3. CALCULATE METRICS
            # improvement_ratio > 0 means complexity was reduced
            improvement = (orig_cc - new_cc) / orig_cc if orig_cc > 0 else 0

            # The Verdict: success means the code is not mathematically worse
            is_better = new_cc <= orig_cc

            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                phase=self.phase,
                data={
                    "original_cc": orig_cc,
                    "new_cc": new_cc,
                    "improvement_ratio": round(improvement, 4),
                    "is_better": is_better,
                },
                duration_sec=time.time() - start_time,
            )
        except Exception as e:
            # LOGGING: Crucial for detecting LLM-induced syntax errors that break Radon
            logger.error(
                "ClarityEvaluator: Radon analysis failed. Possible syntax error in new code: %s",
                e,
            )

            # Fail-closed: If evaluation cannot be performed, the refactor is NOT approved.
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": f"Radon analysis failed (possible syntax error): {e!s}"},
                phase=self.phase,
                confidence=0.0,
            )
