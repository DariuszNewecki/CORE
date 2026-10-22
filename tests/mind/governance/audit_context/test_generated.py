from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.audit_context import AuditorContext


# ID: 933f8efd-cbd8-46ce-b05e-64ab4c9d1326
async def test_AuditorContext_load_knowledge_graph():
    repo_path = Path("/tmp/repo_ktest").resolve()

    mock_intent_repo = MagicMock()
    mock_intent_repo.root = Path("/tmp/law_ktest")

    with (
        patch("mind.logic.engines.registry.EngineRegistry") as mock_engine_registry,
        patch.object(AuditorContext, "_load_governance_resources", return_value={}),
        patch("mind.governance.audit_context.EnforcementMappingLoader"),
        patch(
            "mind.governance.audit_context.KnowledgeService"
        ) as mock_knowledge_service_cls,
    ):
        mock_engine_registry.initialize = MagicMock()

        graph = {"symbols": {"a": {"name": "a"}, "b": {"name": "b"}}}
        mock_service = MagicMock()
        mock_service.get_graph = AsyncMock(return_value=graph)
        mock_knowledge_service_cls.return_value = mock_service

        ctx = AuditorContext(
            repo_path=repo_path,
            intent_repository=mock_intent_repo,
            stateless=False,
        )
        ctx.stateless = False

        await ctx.load_knowledge_graph(force=True)

        mock_service.get_graph.assert_awaited_once()
        assert ctx.knowledge_graph == graph
        assert ctx.symbols_map == {"a": {"name": "a"}, "b": {"name": "b"}}
        assert len(ctx.symbols_list) == 2
