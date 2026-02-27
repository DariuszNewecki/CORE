# src/body/evaluators/base_evaluator.py
# ID: 4b61c8d8-717b-4276-a53b-0f5d23383092
"""Base Evaluator Contract - The "Judge" Interface.

PURIFIED (V2.3.0)
- Removed Will-layer 'DecisionTracer' to satisfy architecture.layers.no_body_to_will.
- Reasoning is now stored in ComponentResult metadata for Will-layer consumption.
- Removed automatic save_trace; Body components must be stateless fact producers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.component_primitive import ComponentResult
from shared.context import CoreContext


# ID: 078fdd48-815b-446e-936b-f0a12846a2ea
class BaseEvaluator(ABC):
    """Base contract for all evaluators operating in the AUDIT phase."""

    def __init__(self, context: CoreContext | None = None) -> None:
        self.context = context

    @property
    @abstractmethod
    # ID: f6a5e1cf-96eb-436f-8c94-611e429db6f8
    def component_id(self) -> str:
        """Unique identifier for this evaluator."""

    @property
    @abstractmethod
    # ID: 9062c5d4-f7db-44ff-ad27-f98758061cb9
    def phase(self) -> str:
        """Execution phase this evaluator belongs to."""

    @abstractmethod
    # ID: fd232b4d-4cc7-4c80-8e2a-dca89d96b16b
    async def evaluate(self, *args: Any, **kwargs: Any) -> ComponentResult:
        """Execute evaluation and return structured result."""

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
