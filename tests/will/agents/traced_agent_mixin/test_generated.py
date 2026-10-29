from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.agents.traced_agent_mixin import TracedAgentMixin


# ID: 511da0ca-1fb0-4a15-ba4c-5d6b0d8f337c
async def test_TracedAgentMixin_save_decision_trace() -> None:
    mixin = TracedAgentMixin.__new__(TracedAgentMixin)
    mock_tracer = MagicMock()
    mock_tracer.save_trace = AsyncMock()
    mixin.tracer = mock_tracer

    await TracedAgentMixin.save_decision_trace(mixin)

    mock_tracer.save_trace.assert_awaited_once_with()


# ID: d79bb05c-0792-4fd5-ad58-d92f4e0a0ae2
def test_TracedAgentMixin_get_decision_trace():
    instance = MagicMock(spec=TracedAgentMixin)
    instance.tracer = MagicMock()
    instance.tracer.explain_chain.return_value = "step 1 -> step 2"

    result = TracedAgentMixin.get_decision_trace(instance)

    instance.tracer.explain_chain.assert_called_once_with()
    assert result == "step 1 -> step 2"


import asyncio


# ID: 5713db61-34b0-44d4-9104-b0b43c646909
def test_TracedAgentMixin():
    tracer = MagicMock()
    tracer.explain_chain = MagicMock(return_value="decision trace output")
    tracer.save_trace = AsyncMock(return_value=None)

    class _Agent(TracedAgentMixin):
        def __init__(self):
            self.tracer = tracer

    agent = _Agent()

    assert agent.get_decision_trace() == "decision trace output"
    tracer.explain_chain.assert_called_once_with()

    asyncio.run(agent.save_decision_trace())
    tracer.save_trace.assert_awaited_once_with()
