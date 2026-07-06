# tests/body/introspection/test_drift_service.py
"""Unit tests for body.introspection.drift_service (ADR-143 D3).

Exercises run_drift_analysis_async() against a mocked ServiceRegistry session
so no real DB connection is required.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from body.introspection.drift_service import run_drift_analysis_async


def _make_session_cm(execute_side_effects: list) -> tuple:
    """Build an async context-manager that yields a session with .execute()
    returning *execute_side_effects* in order."""
    execute_mock = AsyncMock(side_effect=execute_side_effects)

    class _SessionCM:
        async def __aenter__(self):
            return SimpleNamespace(execute=execute_mock)

        async def __aexit__(self, *args):
            return False

    return _SessionCM(), execute_mock


# ID: 4c7e2a91-3f5b-4d08-b1a6-8e9d0c2f7b31
async def test_happy_path_returns_counts_and_timestamp() -> None:
    """All three queries succeed — anchor_violations, pending_symbols, and
    last_sync_at are returned with available=True."""
    ts = datetime.datetime(2026, 7, 6, 10, 0, 0, tzinfo=datetime.UTC)
    anchor_r = SimpleNamespace(scalar=lambda: 3)
    pending_r = SimpleNamespace(scalar=lambda: 7)
    hb_r = SimpleNamespace(fetchone=lambda: (ts,))

    session_cm, _ = _make_session_cm([anchor_r, pending_r, hb_r])

    with patch("body.services.service_registry.ServiceRegistry") as mock_sr:
        mock_sr.session.return_value = session_cm
        result = await run_drift_analysis_async()

    assert result["available"] is True
    assert result["anchor_violations"] == 3
    assert result["pending_symbols"] == 7
    assert result["last_sync_at"] == ts.isoformat()


# ID: 8b3f1d54-a7c2-4e91-9d60-1f2e4b5a8c73
async def test_no_heartbeat_yields_none_last_sync_at() -> None:
    """When DbSyncWorker has never posted a heartbeat, last_sync_at is None."""
    anchor_r = SimpleNamespace(scalar=lambda: 0)
    pending_r = SimpleNamespace(scalar=lambda: 0)
    hb_r = SimpleNamespace(fetchone=lambda: None)

    session_cm, _ = _make_session_cm([anchor_r, pending_r, hb_r])

    with patch("body.services.service_registry.ServiceRegistry") as mock_sr:
        mock_sr.session.return_value = session_cm
        result = await run_drift_analysis_async()

    assert result["available"] is True
    assert result["last_sync_at"] is None


# ID: d2a6e8b1-5f3c-4a70-8e91-9b0d2c3f4a57
async def test_zero_violations_is_clean() -> None:
    """Zero open findings and zero pending symbols → clean drift state."""
    ts = datetime.datetime(2026, 7, 6, 8, 0, 0, tzinfo=datetime.UTC)
    anchor_r = SimpleNamespace(scalar=lambda: 0)
    pending_r = SimpleNamespace(scalar=lambda: 0)
    hb_r = SimpleNamespace(fetchone=lambda: (ts,))

    session_cm, _ = _make_session_cm([anchor_r, pending_r, hb_r])

    with patch("body.services.service_registry.ServiceRegistry") as mock_sr:
        mock_sr.session.return_value = session_cm
        result = await run_drift_analysis_async()

    assert result == {
        "available": True,
        "anchor_violations": 0,
        "pending_symbols": 0,
        "last_sync_at": ts.isoformat(),
    }


# ID: 7f4c9a2e-1b8d-4e50-a3f6-2c5d9e0b8a41
async def test_db_failure_returns_available_false() -> None:
    """DB exception propagated from the session context manager surfaces as
    available=False with an error field — the endpoint still returns 200."""

    class _FailingSessionCM:
        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *args):
            return False

    with patch("body.services.service_registry.ServiceRegistry") as mock_sr:
        mock_sr.session.return_value = _FailingSessionCM()
        result = await run_drift_analysis_async()

    assert result["available"] is False
    assert "RuntimeError" in result["error"]
    assert "connection refused" in result["error"]


# ID: 3e9b5f72-8a1c-4d60-b2e7-4f0c8d1a9b25
async def test_scalar_none_coerces_to_zero() -> None:
    """scalar() returning None (edge case in some PG drivers) is coerced to 0."""
    ts = datetime.datetime(2026, 7, 6, 9, 0, 0, tzinfo=datetime.UTC)
    anchor_r = SimpleNamespace(scalar=lambda: None)
    pending_r = SimpleNamespace(scalar=lambda: None)
    hb_r = SimpleNamespace(fetchone=lambda: (ts,))

    session_cm, _ = _make_session_cm([anchor_r, pending_r, hb_r])

    with patch("body.services.service_registry.ServiceRegistry") as mock_sr:
        mock_sr.session.return_value = session_cm
        result = await run_drift_analysis_async()

    assert result["anchor_violations"] == 0
    assert result["pending_symbols"] == 0
