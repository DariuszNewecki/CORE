# src/will/strategists/clarity_strategist.py

"""
Clarity Strategist - Determines the optimal refactoring path.
"""

from __future__ import annotations

import time

from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.infrastructure.intent.operational_config import load_operational_config
from will.strategists.base_strategist import BaseStrategist


_CFG_CL = load_operational_config().clarity


# ID: bd9fa9a8-ec7c-45b1-9214-0b4bc4ca651f
class ClarityStrategist(BaseStrategist):
    # ID: f17ad5ad-cf0f-4923-92a0-a828097384ab
    async def execute(
        self, complexity_score: int, line_count: int, **kwargs
    ) -> ComponentResult:
        start_time = time.time()

        # Deterministic Strategy Mapping
        if (
            complexity_score > _CFG_CL.structural_complexity
            or line_count > _CFG_CL.structural_lines
        ):
            strategy = "structural_decomposition"
            instruction = (
                "Extract logic into smaller, focused private methods. Reduce nesting."
            )
        elif complexity_score > _CFG_CL.logic_simplification_threshold:
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
