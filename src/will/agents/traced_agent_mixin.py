# src/will/agents/traced_agent_mixin.py
"""TracedAgentMixin - Shared decision trace interface.

Eliminates AST duplication between ExecutionAgent and SpecificationAgent.
Both hold self.tracer = DecisionTracer() and expose identical get_decision_trace
and save_decision_trace methods.

Usage:
    # ID: c9a742bb-eb84-4a3a-86a2-a5f1faeeaa38
    class MyAgent(TracedAgentMixin):
        def __init__(self):
            self.tracer = DecisionTracer()
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from will.orchestration.decision_tracer import DecisionTracer


# ID: 249141fe-0f74-4330-ba2f-358f332a9522
class TracedAgentMixin:
    """Mixin for Will agents that own a DecisionTracer instance.

    Requires subclass to set self.tracer = DecisionTracer() in __init__.
    """

    tracer: DecisionTracer

    # ID: 60bb8d39-35a7-48bb-a7da-6ae4116796c2
    def get_decision_trace(self) -> str:
        """Return formatted decision trace from this agent's tracer."""
        return self.tracer.explain_chain()

    # ID: 85c94fcf-a922-42eb-8475-5781c756ebef
    async def save_decision_trace(self) -> None:
        """Persist the decision trace to disk via the tracer."""
        await self.tracer.save_trace()
