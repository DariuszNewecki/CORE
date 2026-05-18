# tests/api/v1/test_inspect_routes.py

"""Unit tests for inspect_routes — ADR-057 Phase 3, D3.

Read-only endpoints; tests cover that each route forwards to its facade
function and returns the facade's payload unchanged. Closes ADR-057
verification criterion 1 (each endpoint exists and returns governed
responses) for the /inspect surface.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.inspect_routes import (
    analysis_clusters,
    analysis_command_tree,
    analysis_common_knowledge,
    analysis_duplicates,
    analysis_test_targets,
    decisions_list,
    decisions_patterns,
    refusals_list,
    refusals_stats,
    status_db,
    status_drift,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


@pytest.mark.asyncio
async def test_status_db_delegates_to_facade():
    session = MagicMock()
    with patch(
        "api.v1.inspect_routes.get_db_status",
        new=AsyncMock(return_value={"ok": True, "connected": True}),
    ) as facade:
        out = await status_db(session=session)
    facade.assert_awaited_once()
    assert out == {"ok": True, "connected": True}


@pytest.mark.asyncio
async def test_status_drift_passes_scope():
    request = _mock_request_with_context()
    with patch(
        "api.v1.inspect_routes.get_drift_status",
        new=AsyncMock(return_value={"scope": "symbols"}),
    ) as facade:
        out = await status_drift(request=request, scope="symbols")
    _, kwargs = facade.call_args
    assert kwargs["scope"] == "symbols"
    assert out["scope"] == "symbols"


@pytest.mark.asyncio
async def test_decisions_list_passes_filters():
    with patch(
        "api.v1.inspect_routes.get_decisions",
        new=AsyncMock(return_value={"count": 0, "traces": []}),
    ) as facade:
        out = await decisions_list(
            session_id="abc",
            agent="agent-x",
            pattern="extract",
            limit=10,
        )
    _, kwargs = facade.call_args
    assert kwargs["session_id"] == "abc"
    assert kwargs["agent"] == "agent-x"
    assert kwargs["pattern"] == "extract"
    assert kwargs["limit"] == 10
    assert out == {"count": 0, "traces": []}


@pytest.mark.asyncio
async def test_decisions_patterns_passes_days():
    with patch(
        "api.v1.inspect_routes.get_decisions_patterns",
        new=AsyncMock(return_value={"days": 30, "patterns": []}),
    ) as facade:
        out = await decisions_patterns(days=30)
    _, kwargs = facade.call_args
    assert kwargs["days"] == 30
    assert out["days"] == 30


@pytest.mark.asyncio
async def test_refusals_list_passes_filters():
    with patch(
        "api.v1.inspect_routes.get_refusals",
        new=AsyncMock(return_value={"count": 0, "refusals": []}),
    ) as facade:
        out = await refusals_list(
            refusal_type="boundary", session_id=None, limit=5
        )
    _, kwargs = facade.call_args
    assert kwargs["refusal_type"] == "boundary"
    assert kwargs["limit"] == 5
    assert out["count"] == 0


@pytest.mark.asyncio
async def test_refusals_stats_passes_days():
    with patch(
        "api.v1.inspect_routes.get_refusals_stats",
        new=AsyncMock(return_value={"days": 7, "stats": {}, "counts_by_type": {}}),
    ) as facade:
        out = await refusals_stats(days=7)
    _, kwargs = facade.call_args
    assert kwargs["days"] == 7
    assert "stats" in out


@pytest.mark.asyncio
async def test_analysis_clusters_passes_limit():
    with patch(
        "api.v1.inspect_routes.get_analysis_clusters",
        new=AsyncMock(return_value={"available": False, "clusters": []}),
    ) as facade:
        out = await analysis_clusters(limit=10)
    _, kwargs = facade.call_args
    assert kwargs["limit"] == 10
    assert "clusters" in out


@pytest.mark.asyncio
async def test_analysis_duplicates_passes_threshold():
    request = _mock_request_with_context()
    with patch(
        "api.v1.inspect_routes.get_analysis_duplicates",
        new=AsyncMock(return_value={"ok": True, "threshold": 0.9}),
    ) as facade:
        out = await analysis_duplicates(request=request, threshold=0.9)
    _, kwargs = facade.call_args
    assert kwargs["threshold"] == 0.9
    assert out["threshold"] == 0.9


@pytest.mark.asyncio
async def test_analysis_common_knowledge_passes_limit():
    with patch(
        "api.v1.inspect_routes.get_analysis_common_knowledge",
        new=AsyncMock(return_value={"available": False, "candidates": []}),
    ) as facade:
        out = await analysis_common_knowledge(limit=15)
    _, kwargs = facade.call_args
    assert kwargs["limit"] == 15
    assert "candidates" in out


@pytest.mark.asyncio
async def test_analysis_command_tree_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.inspect_routes.get_analysis_command_tree",
        return_value={"available": True, "source": "cli", "count": 0, "commands": []},
    ):
        out = await analysis_command_tree(request=request)
    assert out["available"] is True


@pytest.mark.asyncio
async def test_analysis_test_targets_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.inspect_routes.get_analysis_test_targets",
        return_value={"available": False, "targets": []},
    ):
        out = await analysis_test_targets(request=request)
    assert "targets" in out
