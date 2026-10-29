from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.agents.coder_agent import CoderAgent


@pytest.mark.asyncio
# ID: a7363372-1dfa-4e43-9ca0-94127f7a2aed
async def test_CoderAgent_generate_or_repair():
    # Build the agent instance bypassing the heavy __init__ via object.__new__
    agent = object.__new__(CoderAgent)

    # Mock dependencies used by generate_or_repair
    agent.tracer = MagicMock()
    agent.tracer.save_trace = AsyncMock()

    # Happy path: no pain_signal -> delegate to _generate_initial
    agent._generate_initial = AsyncMock(return_value="generated code")

    task = MagicMock()
    goal = "implement feature X"

    result = await agent.generate_or_repair(task, goal)

    assert result == "generated code"
    agent._generate_initial.assert_awaited_once_with(task, goal)
    agent.tracer.save_trace.assert_awaited_once()
