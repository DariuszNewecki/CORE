from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.agents.strategic_auditor.context_gatherer import SystemContextGatherer


@pytest.mark.asyncio
# ID: 670e93eb-2f0f-46b5-ac44-70342cd62cb9
async def test_SystemContextGatherer_gather():
    context = MagicMock()
    cognitive_service = MagicMock()

    gatherer = SystemContextGatherer(context, cognitive_service)

    gatherer._gather_constitutional_health = AsyncMock(return_value={"findings": []})
    gatherer._gather_structural_health = AsyncMock(return_value={"nodes": 10})
    gatherer._gather_knowledge_gaps = AsyncMock(return_value=["gap1"])
    gatherer._gather_vector_dimensions = AsyncMock(
        return_value=({"semantic": "ok"}, {"drift": 0.1})
    )
    gatherer._gather_change_context = MagicMock(return_value={"delta": "abc"})
    gatherer._gather_constitution_summary = MagicMock(return_value={"articles": 133})

    session = AsyncMock()

    result = await gatherer.gather(session)

    gatherer._gather_constitutional_health.assert_awaited_once_with(session)
    gatherer._gather_structural_health.assert_awaited_once_with(session)
    gatherer._gather_knowledge_gaps.assert_awaited_once_with(session)
    gatherer._gather_vector_dimensions.assert_awaited_once_with(session)
    gatherer._gather_change_context.assert_called_once_with()
    gatherer._gather_constitution_summary.assert_called_once_with()

    assert result["audit_findings"] == {"findings": []}
    assert result["semantic_landscape"] == {"semantic": "ok"}
    assert result["knowledge_gaps"] == ["gap1"]
    assert result["structural_health"] == {"nodes": 10}
    assert result["change_context"] == {"delta": "abc"}
    assert result["intent_drift"] == {"drift": 0.1}
    assert result["knowledge_graph_summary"] == {"nodes": 10}
    assert result["constitution_summary"] == {"articles": 133}
    assert result["git_delta"] == {"delta": "abc"}
    assert "gathered_at" in result
    datetime.fromisoformat(result["gathered_at"])


from unittest.mock import patch


# ID: ff55d0ee-b55d-4d49-ae09-4ba1165c3a24
def test_SystemContextGatherer():
    from will.agents.strategic_auditor.context_gatherer import SystemContextGatherer

    mock_ctx = MagicMock()
    mock_ctx.git_service = MagicMock()
    mock_ctx.git_service.repo_path = "/repo"
    mock_ctx.git_service.get_recent_commits = MagicMock(return_value=["commit1"])
    mock_ctx.git_service.get_diff_stat = MagicMock(return_value="stat")
    mock_ctx.git_service.get_changed_files_log = MagicMock(return_value=["src/a.py"])
    mock_ctx.qdrant_service = AsyncMock()
    mock_ctx.qdrant_service.scroll_all_points = AsyncMock(return_value=[])

    mock_cognitive = MagicMock()

    gatherer = SystemContextGatherer(mock_ctx, mock_cognitive)

    # Mock the async dimension helpers to isolate gather() orchestration
    gatherer._gather_constitutional_health = AsyncMock(return_value=[])
    gatherer._gather_structural_health = AsyncMock(return_value={"total_symbols": 1})
    gatherer._gather_knowledge_gaps = AsyncMock(return_value={"no_intent": 0})
    gatherer._gather_vector_dimensions = AsyncMock(
        return_value=({"total_vectors": 0}, {"symbols_sampled": 0})
    )

    mock_repo = MagicMock()
    mock_repo.list_policies.return_value = []

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        session = AsyncMock()
        result = __import__("asyncio").run(gatherer.gather(session))

    assert isinstance(result, dict)
    assert result["audit_findings"] == []
    assert result["structural_health"] == {"total_symbols": 1}
    assert result["knowledge_gaps"] == {"no_intent": 0}
    assert result["semantic_landscape"] == {"total_vectors": 0}
    assert result["intent_drift"] == {"symbols_sampled": 0}
    assert result["knowledge_graph_summary"] == result["structural_health"]
    assert result["git_delta"] == result["change_context"]
    assert result["constitution_summary"] == {"policy_count": 0, "policy_ids": []}
    assert "gathered_at" in result

    gatherer._gather_constitutional_health.assert_awaited_once_with(session)
    gatherer._gather_structural_health.assert_awaited_once_with(session)
    gatherer._gather_knowledge_gaps.assert_awaited_once_with(session)
    gatherer._gather_vector_dimensions.assert_awaited_once_with(session)



import pytest


@pytest.mark.asyncio
# ID: d783497b-568f-4886-8997-8750c09b133b
async def test_gather():
    context = MagicMock()
    cognitive_service = MagicMock()
    gatherer = SystemContextGatherer(context, cognitive_service)

    gatherer._gather_constitutional_health = AsyncMock(return_value={"a": 1})
    gatherer._gather_structural_health = AsyncMock(return_value={"s": 2})
    gatherer._gather_knowledge_gaps = AsyncMock(return_value={"k": 3})
    gatherer._gather_vector_dimensions = AsyncMock(
        return_value=({"sem": 4}, {"drift": 5})
    )
    gatherer._gather_change_context = MagicMock(return_value={"c": 6})
    gatherer._gather_constitution_summary = MagicMock(return_value={"sum": 7})

    session = AsyncMock()

    result = await gatherer.gather(session)

    assert result["audit_findings"] == {"a": 1}
    assert result["structural_health"] == {"s": 2}
    assert result["knowledge_gaps"] == {"k": 3}
    assert result["semantic_landscape"] == {"sem": 4}
    assert result["intent_drift"] == {"drift": 5}
    assert result["change_context"] == {"c": 6}
    assert result["knowledge_graph_summary"] == {"s": 2}
    assert result["constitution_summary"] == {"sum": 7}
    assert result["git_delta"] == {"c": 6}
    assert "gathered_at" in result

    gatherer._gather_constitutional_health.assert_awaited_once_with(session)
    gatherer._gather_structural_health.assert_awaited_once_with(session)
    gatherer._gather_knowledge_gaps.assert_awaited_once_with(session)
    gatherer._gather_vector_dimensions.assert_awaited_once_with(session)
    gatherer._gather_change_context.assert_called_once()
    gatherer._gather_constitution_summary.assert_called_once()
