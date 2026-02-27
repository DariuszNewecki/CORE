from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.context.builder import ContextBuilder
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService


class _VectorProviderStub:
    async def search_similar(self, summary: str, top_k: int = 5) -> list[dict]:
        return [
            {
                "name": "vector_hit_symbol",
                "path": "",
                "item_type": "symbol",
                "summary": f"hit for {summary}",
            }
        ]


class _BrokenWorkspace:
    def exists(self, path: str) -> bool:
        return True

    def read_text(self, path: str) -> str:
        return ""

    def list_files(self, directory: str, pattern: str) -> list[str]:
        raise RuntimeError("workspace scan failed")


def test_knowledge_graph_builder_compat_export_is_available() -> None:
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeGraphBuilder

    builder = KnowledgeGraphBuilder(Path("."))
    assert hasattr(builder, "build")


@pytest.mark.asyncio
async def test_context_builder_degrades_graph_only_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shared.infrastructure.context import builder as builder_module

    async def _raise_import_error(self) -> dict:  # pragma: no cover - test stub
        raise ImportError("cannot import name 'KnowledgeGraphBuilder'")

    monkeypatch.setattr(
        builder_module.KnowledgeService, "get_graph", _raise_import_error
    )

    context_builder = ContextBuilder(
        db_provider=None,
        vector_provider=_VectorProviderStub(),
        ast_provider=None,
        config={},
        workspace=None,
    )

    packet = await context_builder.build_for_task(
        {
            "task_id": "graph_fallback",
            "task_type": "code_generation",
            "summary": "add validation",
            "scope": {"traversal_depth": 2, "include": []},
            "constraints": {"max_tokens": 5000, "max_items": 5},
        }
    )

    assert "context" in packet
    assert packet["context"], "Non-graph context should still be present"
    assert packet["context"][0]["name"] == "vector_hit_symbol"


@pytest.mark.asyncio
async def test_knowledge_service_workspace_graph_failure_returns_empty_graph() -> None:
    service = KnowledgeService(repo_path=Path("."), workspace=_BrokenWorkspace())

    graph = await service.get_graph()

    assert graph.get("symbols") == {}
