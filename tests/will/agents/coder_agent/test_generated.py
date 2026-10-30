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


from pathlib import Path
from unittest.mock import patch


# ID: e02a5881-5286-4635-a8df-94827c184f7c
def test_CoderAgent(tmp_path: Path) -> None:
    cognitive_service = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    cognitive_service.get_embedding_for_code = AsyncMock(return_value=[0.5, 0.5])
    executor = MagicMock()
    prompt_pipeline = MagicMock()
    auditor_context = MagicMock()
    repo_root = tmp_path

    mock_path_resolver = MagicMock()
    mock_tracer = MagicMock()

    with (
        patch(
            "will.agents.coder_agent.PathResolver.from_repo",
            return_value=mock_path_resolver,
        ),
        patch(
            "will.agents.coder_agent.get_intent_guard",
            return_value=MagicMock(),
        ),
        patch(
            "will.agents.coder_agent.DecisionTracer",
            return_value=mock_tracer,
        ),
        patch(
            "will.agents.coder_agent.PatternValidator",
            return_value=MagicMock(),
        ),
        patch(
            "will.agents.coder_agent.CodeGenerator",
            return_value=MagicMock(),
        ),
    ):
        agent = CoderAgent(
            cognitive_service=cognitive_service,
            executor=executor,
            prompt_pipeline=prompt_pipeline,
            auditor_context=auditor_context,
            repo_root=repo_root,
        )

    assert agent.cognitive_service is cognitive_service
    assert agent.executor is executor
    assert agent.prompt_pipeline is prompt_pipeline
    assert agent.auditor_context is auditor_context
    assert agent.repo_root == repo_root.resolve()
    assert agent.tracer is mock_tracer
