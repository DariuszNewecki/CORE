# tests/api/v1/test_integration_routes.py

"""Unit tests for integration_routes (ADR-054 Phase 1).

POST /integrate is synchronous from the caller's perspective. A failed
workflow translates to 502 — not 200 — so the CLI can render a clear error.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.v1.integration_routes import IntegrateRequest, integrate


def _mock_request():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


async def test_integrate_returns_result_on_success():
    """Successful workflow returns the runner result dict directly."""
    result = {
        "ok": True,
        "commit_sha": "abc1234def5678",
        "staged_files": ["src/body/foo.py"],
    }
    with patch(
        "api.v1.integration_routes.run_integration",
        new=AsyncMock(return_value=result),
    ) as mock_run:
        out = await integrate(
            payload=IntegrateRequest(commit_message="fix: update foo"),
            request=_mock_request(),
        )

    mock_run.assert_awaited_once()
    assert out == result


async def test_integrate_raises_502_on_workflow_failure():
    """Failed workflow (ok=False) becomes HTTPException(502).

    The runner's error message is surfaced in the detail so the CLI
    can render it meaningfully.
    """
    with patch(
        "api.v1.integration_routes.run_integration",
        new=AsyncMock(return_value={"ok": False, "error": "ruff check failed"}),
    ):
        with pytest.raises(HTTPException) as exc:
            await integrate(
                payload=IntegrateRequest(commit_message="chore: cleanup"),
                request=_mock_request(),
            )

    assert exc.value.status_code == 502
    assert "ruff check failed" in exc.value.detail


async def test_integrate_forwards_commit_message_to_runner():
    """The commit_message from the payload is forwarded to run_integration."""
    with patch(
        "api.v1.integration_routes.run_integration",
        new=AsyncMock(return_value={"ok": True}),
    ) as mock_run:
        await integrate(
            payload=IntegrateRequest(commit_message="feat: add widget"),
            request=_mock_request(),
        )

    _, commit_msg_arg = mock_run.call_args.args
    assert commit_msg_arg == "feat: add widget"
