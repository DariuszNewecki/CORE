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
