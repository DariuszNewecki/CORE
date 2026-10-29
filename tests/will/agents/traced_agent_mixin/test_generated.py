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
