# tests/api/v1/test_symbols_routes.py

"""Tests for symbols routes — mock KnowledgeService and drift_service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.symbols_routes import list_unassigned_symbols, symbols_drift


# ---------------------------------------------------------------------------
# list_unassigned_symbols
# ---------------------------------------------------------------------------


async def test_list_unassigned_empty_graph():
    svc = MagicMock()
    svc.get_graph = AsyncMock(return_value={"symbols": {}})
    with patch(
        "api.v1.symbols_routes.KnowledgeService", return_value=svc
    ):
        result = await list_unassigned_symbols(session=MagicMock())
    assert result == {"unassigned": [], "count": 0}


async def test_list_unassigned_skips_private_symbols():
    svc = MagicMock()
    svc.get_graph = AsyncMock(
        return_value={
            "symbols": {
                "k1": {
                    "name": "_private_fn",
                    "file_path": "src/foo.py",
                    "capability": "unassigned",
                },
            }
        }
    )
    with patch("api.v1.symbols_routes.KnowledgeService", return_value=svc):
        result = await list_unassigned_symbols(session=MagicMock())
    assert result["count"] == 0


async def test_list_unassigned_skips_test_files():
    svc = MagicMock()
    svc.get_graph = AsyncMock(
        return_value={
            "symbols": {
                "k1": {
                    "name": "test_helper",
                    "file_path": "tests/api/test_foo.py",
                    "capability": "unassigned",
                },
            }
        }
    )
    with patch("api.v1.symbols_routes.KnowledgeService", return_value=svc):
        result = await list_unassigned_symbols(session=MagicMock())
    assert result["count"] == 0


async def test_list_unassigned_returns_unassigned_public_symbols():
    svc = MagicMock()
    svc.get_graph = AsyncMock(
        return_value={
            "symbols": {
                "k1": {
                    "name": "my_function",
                    "file_path": "src/body/foo.py",
                    "capability": "unassigned",
                },
                "k2": {
                    "name": "assigned_fn",
                    "file_path": "src/body/bar.py",
                    "capability": "code_generation",
                },
            }
        }
    )
    with patch("api.v1.symbols_routes.KnowledgeService", return_value=svc):
        result = await list_unassigned_symbols(session=MagicMock())
    assert result["count"] == 1
    assert result["unassigned"][0]["name"] == "my_function"


async def test_list_unassigned_skips_none_name():
    svc = MagicMock()
    svc.get_graph = AsyncMock(
        return_value={
            "symbols": {
                "k1": {"name": None, "file_path": "src/foo.py", "capability": "unassigned"},
            }
        }
    )
    with patch("api.v1.symbols_routes.KnowledgeService", return_value=svc):
        result = await list_unassigned_symbols(session=MagicMock())
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# symbols_drift
# ---------------------------------------------------------------------------


async def test_symbols_drift_returns_pipeline_data():
    expected = {
        "available": True,
        "anchor_violations": 3,
        "pending_symbols": 1,
        "last_sync_at": "2026-07-11T10:00:00",
    }
    with patch(
        "api.v1.symbols_routes.run_drift_analysis_async",
        new=AsyncMock(return_value=expected),
    ):
        result = await symbols_drift()
    assert result["anchor_violations"] == 3


async def test_symbols_drift_returns_unavailable_on_error():
    expected = {"available": False, "error": "DB connection failed"}
    with patch(
        "api.v1.symbols_routes.run_drift_analysis_async",
        new=AsyncMock(return_value=expected),
    ):
        result = await symbols_drift()
    assert result["available"] is False
