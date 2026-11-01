from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.tagger_agent import CapabilityTaggerAgent


# ID: 021c6b21-85a8-475a-ae69-165de730077b
def test_suggest_and_apply_tags():
    cognitive_service = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    knowledge_service = MagicMock()

    graph = {
        "symbols": {
            "a": {"key": "a", "file_path": "src/foo.py"},
            "b": {"key": "b", "file_path": "src/bar.py"},
        }
    }
    knowledge_service.get_graph = AsyncMock(return_value=graph)

    with (
        patch("will.agents.tagger_agent.PromptModel.load", return_value=MagicMock()),
        patch("will.agents.tagger_agent.DecisionTracer", return_value=MagicMock()),
        patch(
            "will.agents.tagger_agent.ThrottledParallelProcessor"
        ) as mock_processor_cls,
    ):
        agent = CapabilityTaggerAgent(cognitive_service, knowledge_service)

        orphaned = [{"key": "a", "file_path": "src/foo.py"}]
        agent._get_existing_capabilities = AsyncMock(return_value={})
        agent._find_orphaned_symbols = MagicMock(return_value=orphaned)
        agent._get_suggestion_for_symbol = AsyncMock(
            return_value={"key": "a", "suggestion": "SomeCapability"}
        )

        processor = MagicMock()
        processor.run_async = AsyncMock(
            return_value=[{"key": "a", "suggestion": "SomeCapability"}]
        )
        mock_processor_cls.return_value = processor

        result = asyncio.run(agent.suggest_and_apply_tags())

        assert result == {"a": {"key": "a", "suggestion": "SomeCapability"}}
        cognitive_service.aget_client_for_role.assert_awaited_once()
        knowledge_service.get_graph.assert_awaited_once()
        processor.run_async.assert_awaited_once()
