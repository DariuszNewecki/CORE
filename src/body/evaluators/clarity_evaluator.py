# src/body/evaluators/clarity_evaluator.py
# ID: 7fcecf85-269a-419c-81a3-30b1fea807b8
"""Clarity Evaluator - Measures mathematical improvement in code structure.

PURIFIED (V2.7.4)
- Removed Will-layer 'DecisionTracer' dependency.
- Rationale is returned in metadata for the CoderAgent to trace.
"""

from __future__ import annotations

import time

from radon.visitors import ComplexityVisitor

from shared.component_primitive import ComponentResult
from shared.logger import getLogger

from .base_evaluator import BaseEvaluator


logger = getLogger(__name__)


# ID: d4aa43cb-e62b-4a50-b34e-9aa12144a561
class ClarityEvaluator(BaseEvaluator):
    """Evaluate refactoring results by comparing Cyclomatic Complexity (CC)."""

    # ID: c35226bd-1d63-46fc-9ceb-f3c5a1d63208
    async def execute(
        self, original_code: str, new_code: str, **kwargs
    ) -> ComponentResult:
        """Calculate improvement ratio between two versions of code."""
        start_time = time.time()

        try:
            # 1) Sensation: analyze original
            orig_visitor = ComplexityVisitor.from_code(original_code)
            orig_cc = sum(block.complexity for block in orig_visitor.blocks)

            # 2) Sensation: analyze proposed
            new_visitor = ComplexityVisitor.from_code(new_code)
            new_cc = sum(block.complexity for block in new_visitor.blocks)

            # 3) Analysis: calculate metrics
            improvement = (orig_cc - new_cc) / orig_cc if orig_cc > 0 else 0.0
            is_better = new_cc <= orig_cc

            duration = time.time() - start_time

            # 4) Final verdict: rationale moves to metadata
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
                    f"Better: {is_better}"
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
