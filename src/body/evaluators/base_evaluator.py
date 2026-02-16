# src/body/evaluators/base_evaluator.py
# ID: 4b61c8d8-717b-4276-a53b-0f5d23383092
"""Base Evaluator Contract - The "Judge" Interface.

PURIFIED (V2.3.0)
- Removed Will-layer 'DecisionTracer' to satisfy architecture.layers.no_body_to_will.
- Reasoning is now stored in ComponentResult metadata for Will-layer consumption.
- Removed automatic save_trace; Body components must be stateless fact producers.
"""

from __future__ import annotations

from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.context import CoreContext


# ID: 078fdd48-815b-446e-936b-f0a12846a2ea
class BaseEvaluator(Component):
    """Base contract for all evaluators operating in the AUDIT phase."""

    def __init__(self, context: CoreContext | None = None) -> None:
        self.context = context

    @property
    # ID: 0a179fdc-81a2-4cb5-bd3f-a1a23943180e
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    async def _create_result(
        self,
        ok: bool,
        data: dict[str, Any],
        confidence: float,
        duration: float,
        rationale: str | None = None,
    ) -> ComponentResult:
        """Structure results and embed rationale into metadata."""
        metadata = data.get("metadata", {})

        if rationale:
            metadata["rationale"] = rationale

        return ComponentResult(
            component_id=self.component_id,
            ok=ok,
            data=data,
            phase=self.phase,
            confidence=confidence,
            duration_sec=duration,
            metadata=metadata,
        )
