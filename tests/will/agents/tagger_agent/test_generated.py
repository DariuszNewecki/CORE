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


# ID: a3fd2683-c305-4cab-973c-4727325d865b
def test_CapabilityTaggerAgent():
    cognitive_service = MagicMock()
    knowledge_service = MagicMock()

    fake_manifest = MagicMock()
    fake_manifest.role = "tagger"
    fake_prompt_model = MagicMock()
    fake_prompt_model.manifest = fake_manifest

    fake_tracer = MagicMock()

    with (
        patch(
            "will.agents.tagger_agent.PromptModel.load", return_value=fake_prompt_model
        ) as mock_load,
        patch(
            "will.agents.tagger_agent.DecisionTracer", return_value=fake_tracer
        ) as mock_tracer_cls,
    ):
        agent = CapabilityTaggerAgent(
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            entry_point_patterns=[],
        )

    mock_load.assert_called_once_with("capability_definer")
    mock_tracer_cls.assert_called_once()
    assert agent.cognitive_service is cognitive_service
    assert agent.knowledge_service is knowledge_service
    assert agent.prompt_model is fake_prompt_model
    assert agent.tracer is fake_tracer
    assert agent.entry_point_patterns == []
    assert agent.tagger_client is None





# ID: 0e7cf478-fcfd-4869-8e12-39cb1b5036a9
async def test_CapabilityTaggerAgent_suggest_and_apply_tags():
    cognitive_service = MagicMock()
    knowledge_service = MagicMock()

    with (
        patch("will.agents.tagger_agent.PromptModel") as mock_prompt_model_cls,
        patch("will.agents.tagger_agent.DecisionTracer"),
        patch(
            "will.agents.tagger_agent.ThrottledParallelProcessor"
        ) as mock_processor_cls,
    ):
        mock_prompt_model = MagicMock()
        mock_prompt_model.manifest.role = "tagger"
        mock_prompt_model_cls.load.return_value = mock_prompt_model

        agent = CapabilityTaggerAgent(
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
        )

        agent.tagger_client = MagicMock()

        agent._get_existing_capabilities = AsyncMock(return_value={"cap1": {}})
        agent._find_orphaned_symbols = MagicMock(
            return_value=[{"key": "sym1", "file_path": "a.py"}]
        )
        agent._get_suggestion_for_symbol = AsyncMock(
            return_value={"key": "sym1", "tags": ["x"]}
        )

        knowledge_service.get_graph = AsyncMock(
            return_value={"symbols": {"sym1": {"key": "sym1", "file_path": "a.py"}}}
        )

        # Make the processor invoke the worker_fn over the items so the
        # agent's _get_suggestion_for_symbol path is actually exercised.
        # ID: 699ea5fa-1484-4aa9-9b0b-1aad5757bb7e
        async def fake_run_async(items, worker_fn):
            results = []
            for item in items:
                results.append(await worker_fn(item))
            return results

        mock_processor = MagicMock()
        mock_processor.run_async = AsyncMock(side_effect=fake_run_async)
        mock_processor_cls.return_value = mock_processor

        result = await agent.suggest_and_apply_tags()

        assert result == {"sym1": {"key": "sym1", "tags": ["x"]}}
        knowledge_service.get_graph.assert_awaited_once()
        agent._get_suggestion_for_symbol.assert_awaited_once()
