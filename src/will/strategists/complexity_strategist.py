# src/will/strategists/complexity_strategist.py
# ID: f876296e-4f59-4729-871e-b9f14298a4b6

"""
Complexity Strategist - RUNTIME Phase Component.
Determines the optimal path for reducing Cyclomatic Complexity.
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.logger import getLogger
from will.strategists.base_strategist import BaseStrategist


logger = getLogger(__name__)


# ID: b8b66368-91ae-4600-aff4-252735448376
class ComplexityStrategist(BaseStrategist):
    """
    Decides the refactoring strategy for high-complexity code.
    """

    # ID: cf03930a-ff10-4d20-949a-45a3064f57e6
    async def execute(self, complexity_score: int, **kwargs: Any) -> ComponentResult:
        start_time = time.time()

        # Deterministic Complexity Mapping
        if complexity_score > 30:
            strategy = "structural_fragmentation"
            instruction = "This function is a 'God Method'. Extract logic into at least 3 smaller, private helper methods."
        elif complexity_score > 15:
            strategy = "component_extraction"
            instruction = "Extract the main conditional logic into a separate strategy class or validator."
        else:
            strategy = "logic_simplification"
            instruction = "The complexity is moderate. Focus on removing nested if/else blocks and using guard clauses."

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            phase=self.phase,
            data={
                "strategy": strategy,
                "instruction": instruction,
                "target_reduction": 0.3,  # We want a 30% reduction for complexity tasks
            },
            duration_sec=time.time() - start_time,
        )
