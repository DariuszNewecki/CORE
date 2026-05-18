# tests/api/v1/test_daemon_routes.py

"""Unit tests for daemon_routes — ADR-058 Phase 4, D3.

Covers ADR-058 verification criteria 5 (POST /daemon/stop returns 200
before systemctl stop executes — confirmed via BackgroundTask
scheduling) and 6 (GET /daemon/status returns governed worker health
data).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from api.v1.daemon_routes import daemon_start, daemon_status, daemon_stop


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


@pytest.mark.asyncio
async def test_daemon_status_returns_facade_payload():
    """GET /daemon/status returns the WorkerRegistryService-derived shape."""
    request = _mock_request_with_context()
    payload = {
        "available": True,
        "alive_threshold_sec": 600,
        "worker_count": 12,
        "alive_count": 12,
        "workers": [
            {"name": "AuditViolationSensor", "alive": True, "phase": "audit"},
        ],
    }
    with patch(
        "api.v1.daemon_routes.get_status",
        new=AsyncMock(return_value=payload),
    ) as facade:
        out = await daemon_status(request=request)
    facade.assert_awaited_once()
    assert out == payload


@pytest.mark.asyncio
async def test_daemon_start_returns_started_on_success():
    """POST /daemon/start delegates to start_daemon and returns 'started'."""
    request = _mock_request_with_context()
    with patch(
        "api.v1.daemon_routes.start_daemon",
        new=AsyncMock(return_value={"ok": True, "exit_code": 0}),
    ) as facade:
        out = await daemon_start(request=request)
    facade.assert_awaited_once()
    assert out == {"status": "started", "exit_code": 0}


@pytest.mark.asyncio
async def test_daemon_start_returns_500_on_systemctl_failure():
    """systemctl failure → 500 with detail."""
    request = _mock_request_with_context()
    with patch(
        "api.v1.daemon_routes.start_daemon",
        new=AsyncMock(
            return_value={
                "ok": False,
                "exit_code": 1,
                "stderr_tail": ["Unit core-daemon.service not found."],
            }
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await daemon_start(request=request)
    assert exc.value.status_code == 500
    assert exc.value.detail["error"] == "daemon_start_failed"


@pytest.mark.asyncio
async def test_daemon_stop_returns_200_before_systemctl_runs():
    """POST /daemon/stop schedules stop_daemon_background and returns 200
    immediately. The systemctl stop call MUST run via BackgroundTask, not
    inline — verified by asserting background_tasks.add_task was called and
    stop_daemon_background was NOT awaited during the handler. Closes
    ADR-058 V5."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 0
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    with patch(
        "api.v1.daemon_routes.stop_daemon_background", new=AsyncMock()
    ) as stop_mock:
        out = await daemon_stop(
            request=request,
            response=response,
            background_tasks=background_tasks,
        )

    assert out == {"status": "stopping"}
    assert response.status_code == 200
    # The handler must register the BackgroundTask but MUST NOT await it.
    stop_mock.assert_not_awaited()
    background_tasks.add_task.assert_called_once_with(stop_mock)
