# src/will/agents/traced_agent_mixin.py
# ID: c1d2e3f4-a5b6-7890-cdef-012345678901
"""TracedAgentMixin - Shared decision trace interface.

Eliminates AST duplication between ExecutionAgent and SpecificationAgent.
Both hold self.tracer = DecisionTracer() and expose identical get_decision_trace
and save_decision_trace methods.

Usage:
    class MyAgent(TracedAgentMixin):
        def __init__(self):
            self.tracer = DecisionTracer()
"""

from __future__ import annotations


# ID: d2e3f4a5-b6c7-8901-defa-123456789012
class TracedAgentMixin:
    """Mixin for Will agents that own a DecisionTracer instance.

    Requires subclass to set self.tracer = DecisionTracer() in __init__.
    """

    # ID: e3f4a5b6-c7d8-9012-efab-234567890123
    def get_decision_trace(self) -> str:
        """Return formatted decision trace from this agent's tracer."""
        return self.tracer.format_trace()

    # ID: f4a5b6c7-d8e9-0123-fabc-345678901234
    def save_decision_trace(self) -> None:
        """Persist the decision trace to disk via the tracer."""
        self.tracer.save_trace()
