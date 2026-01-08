# src/will/strategists/clarity_strategist.py

"""
Clarity Strategist - Determines the optimal refactoring path.
"""

from __future__ import annotations

import time

from shared.component_primitive import Component, ComponentPhase, ComponentResult


# ID: bd9fa9a8-ec7c-45b1-9214-0b4bc4ca651f
class ClarityStrategist(Component):
    @property
    # ID: 983b29a1-543b-4cd9-ab3f-9845ac93c05d
    def phase(self) -> ComponentPhase:
        return ComponentPhase.RUNTIME

    # ID: f17ad5ad-cf0f-4923-92a0-a828097384ab
    async def execute(
        self, complexity_score: int, line_count: int, **kwargs
    ) -> ComponentResult:
        start_time = time.time()

        # Deterministic Strategy Mapping
        if complexity_score > 20 or line_count > 300:
            strategy = "structural_decomposition"
            instruction = (
                "Extract logic into smaller, focused private methods. Reduce nesting."
            )
        elif complexity_score > 10:
            strategy = "logic_simplification"
            instruction = "Simplify boolean expressions and consolidate redundant conditional branches."
        else:
            strategy = "readability_polish"
            instruction = (
                "Improve variable naming and add clarifying comments to complex blocks."
            )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            phase=self.phase,
            data={
                "strategy": strategy,
                "instruction": instruction,
                "target_complexity_reduction": 0.2,  # We want at least 20% improvement
            },
            duration_sec=time.time() - start_time,
        )
