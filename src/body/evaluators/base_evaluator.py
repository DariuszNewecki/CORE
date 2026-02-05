# src/body/evaluators/base_evaluator.py
# ID: evaluator.base_contract

"""
Base Evaluator Contract - The "Judge" Interface.

HEALED (V2.7.1):
- Auto-Persistence: Now automatically saves the decision trace to the DB
  at the end of every execution.
"""

from __future__ import annotations

from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.context import CoreContext
from will.orchestration.decision_tracer import DecisionTracer


# ID: 4b61c8d8-717b-4276-a53b-0f5d23383092
class BaseEvaluator(Component):
    def __init__(self, context: CoreContext | None = None):
        self.context = context
        # Standardized Tracing
        self.tracer = DecisionTracer(
            path_resolver=context.path_resolver if context else None,
            agent_name=self.__class__.__name__,
        )

    @property
    # ID: 0a179fdc-81a2-4cb5-bd3f-a1a23943180e
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    async def _create_result(
        self, ok: bool, data: dict[str, Any], confidence: float, duration: float
    ) -> ComponentResult:
        """Helper to structure results and PERMANENTLY save the trace."""

        # HEALED: Before returning the result, save the history to the Database
        try:
            await self.tracer.save_trace()
        except Exception:
            pass  # Fail-safe: don't crash if DB is busy

        return ComponentResult(
            component_id=self.component_id,
            ok=ok,
            data=data,
            phase=self.phase,
            confidence=confidence,
            duration_sec=duration,
        )
