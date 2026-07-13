# tests/api/v1/test_onboard_routes.py

"""Tests for BYOR onboarding routes — mock cli.logic.byor dependencies.

Split from test_project_routes.py alongside the onboard_routes.py extraction
(#782).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.onboard_routes import onboard_project, promote_onboard


def _make_request(repo_path: str = "/opt/dev/CORE") -> MagicMock:
    req = MagicMock()
    req.app.state.core_context.git_service.repo_path = Path(repo_path)
    return req


# ---------------------------------------------------------------------------
# onboard_project
# ---------------------------------------------------------------------------


async def test_onboard_dry_run():
    from api.v1.onboard_routes import OnboardRequest

    body = OnboardRequest(path="/tmp/myrepo", write=False)
    request = _make_request()

    with patch(
        "cli.logic.byor.initialize_repository", new=AsyncMock(return_value=None)
    ) as mock_init:
        result = await onboard_project(body=body, request=request)

    assert result["mode"] == "dry-run"
    mock_init.assert_awaited_once()


async def test_onboard_returns_400_on_typer_exit():
    """typer.Exit is click.exceptions.Exit -> RuntimeError, NOT SystemExit —
    catching only SystemExit silently lets every known byor.py failure mode
    (missing/existing .intent/, inaccessible target path) fall through to the
    generic 500 branch. Regression coverage for that mapping."""
    import typer
    from fastapi import HTTPException

    from api.v1.onboard_routes import OnboardRequest

    body = OnboardRequest(path="/tmp/myrepo", write=True)
    request = _make_request()

    with patch(
        "cli.logic.byor.initialize_repository",
        new=AsyncMock(side_effect=typer.Exit(code=1)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await onboard_project(body=body, request=request)
    assert exc_info.value.status_code == 400


async def test_onboard_stage_without_write_returns_early():
    from api.v1.onboard_routes import OnboardRequest

    body = OnboardRequest(path="/tmp/myrepo", write=False, stage=True)
    request = _make_request()

    result = await onboard_project(body=body, request=request)
    assert result["mode"] == "dry-run"
    assert "note" in result


# ---------------------------------------------------------------------------
# promote_onboard
# ---------------------------------------------------------------------------


async def test_promote_ok():
    from api.v1.onboard_routes import PromoteRequest

    body = PromoteRequest(path="/tmp/myrepo")
    request = _make_request()

    with patch("cli.logic.byor.promote_staged", new=AsyncMock(return_value=None)):
        result = await promote_onboard(body=body, request=request)

    assert result["promoted"] is True


async def test_promote_returns_400_on_typer_exit():
    import typer
    from fastapi import HTTPException

    from api.v1.onboard_routes import PromoteRequest

    body = PromoteRequest(path="/tmp/missing")
    request = _make_request()

    with patch(
        "cli.logic.byor.promote_staged",
        new=AsyncMock(side_effect=typer.Exit(code=1)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await promote_onboard(body=body, request=request)
    assert exc_info.value.status_code == 400
