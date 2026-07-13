from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.capability_tagger import CapabilityTaggerWorker


# ID: f02a0266-aa61-41d5-9109-8c6970a75551
async def test_CapabilityTaggerWorker():
    # Setup mocks for external dependencies
    mock_cognitive_service = MagicMock()

    # Patch local imports — these are imported inside methods, so we patch at their defining module
    with (
        patch("body.services.service_registry.service_registry") as mock_registry,
        patch(
            "shared.infrastructure.knowledge.knowledge_service.KnowledgeService"
        ) as mock_knowledge_service,
        patch("will.agents.tagger_agent.CapabilityTaggerAgent") as mock_agent_class,
        patch("will.workers.capability_tagger._CFG") as mock_cfg,
    ):
        # Configure mock config
        mock_cfg.batch_size = 5

        # Configure mock symbol service
        mock_symbol_service = AsyncMock()
        mock_registry.get_symbol_service = AsyncMock(return_value=mock_symbol_service)

        # Configure mock untagged symbols
        untagged_symbols = [
            {"id": "uuid-1", "symbol_path": "module1.Symbol1", "name": "Symbol1"},
            {"id": "uuid-2", "symbol_path": "module2.Symbol2", "name": "Symbol2"},
        ]
        mock_symbol_service.fetch_untagged_symbols = AsyncMock(
            return_value=untagged_symbols
        )

        # Configure mock agent
        mock_agent = AsyncMock()
        mock_agent_class.return_value = mock_agent

        # Configure suggestions returned by agent
        suggestions = {
            "key1": {
                "key": "uuid-1",
                "suggestion": "capability.math",
                "name": "Symbol1",
            },
            "key2": {
                "key": "uuid-2",
                "suggestion": "capability.io",
                "name": "Symbol2",
            },
        }
        mock_agent.suggest_and_apply_tags = AsyncMock(return_value=suggestions)

        # Configure mock knowledge service
        mock_knowledge_service_instance = MagicMock()
        mock_knowledge_service.return_value = mock_knowledge_service_instance

        # Create worker instance
        worker = CapabilityTaggerWorker(cognitive_service=mock_cognitive_service)

        # Mock post_* methods on the worker instance
        worker.post_heartbeat = AsyncMock()
        worker.post_report = AsyncMock()
        worker._repo_root = "/fake/repo/root"

        # Execute the run method
        await worker.run()

        # Assertions
        worker.post_heartbeat.assert_awaited_once()

        # Verify we fetched untagged symbols
        mock_symbol_service.fetch_untagged_symbols.assert_awaited_once_with(5)

        # Verify agent was called with correct limit
        mock_agent.suggest_and_apply_tags.assert_awaited_once_with(limit=5)

        # Verify symbol keys were applied
        mock_symbol_service.apply_symbol_keys.assert_awaited_once_with(
            [
                {"id": "uuid-1", "key": "capability.math"},
                {"id": "uuid-2", "key": "capability.io"},
            ]
        )

        # Verify report was posted
        worker.post_report.assert_awaited_once_with(
            subject="capability_tagger.run.complete",
            payload={
                "tagged": 2,
                "processed": 2,
            },
        )
