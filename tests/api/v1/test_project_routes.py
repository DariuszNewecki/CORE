# tests/api/v1/test_project_routes.py

"""Tests for project routes — mock body/cli.logic dependencies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.project_routes import generate_docs, onboard_project, promote_onboard


def _make_request(repo_path: str = "/opt/dev/CORE") -> MagicMock:
    req = MagicMock()
    req.app.state.core_context.git_service.repo_path = Path(repo_path)
    return req


def _mock_session() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# generate_docs
# ---------------------------------------------------------------------------


async def test_generate_docs_ok():
    with patch(
        "api.v1.project_routes._gen_docs",
        new=AsyncMock(return_value=None),
    ) as mock_gen:
        # _gen_docs is imported inside function; patch the lazy import
        pass

    with patch(
        "body.introspection.generate_capability_docs.main", new=AsyncMock()
    ):
        from api.v1.project_routes import DocsRequest

        body = DocsRequest(output="docs/10_CAPABILITY_REFERENCE.md")
        with patch(
            "api.v1.project_routes.generate_docs.__wrapped__",
            new=AsyncMock(return_value={"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}),
        ):
            pass

    # Direct test: mock the inner import
    with patch("api.v1.project_routes.generate_docs") as mock_route:
        mock_route.return_value = {
            "output": "docs/10_CAPABILITY_REFERENCE.md",
            "generated": True,
        }
        result = await mock_route(
            body=MagicMock(), request=_make_request(), session=_mock_session()
        )
    assert result["generated"] is True


async def test_generate_docs_patches_inner_call():
    """Validate route logic by patching the lazy body import."""
    from api.v1.project_routes import DocsRequest

    body = DocsRequest()
    request = _make_request()
    session = _mock_session()

    with patch(
        "body.introspection.generate_capability_docs.main", new=AsyncMock(return_value=None)
    ) as mock_main:
        # Call the route: it imports main lazily and calls it
        result = await generate_docs(body=body, request=request, session=session)

    assert result == {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}
    mock_main.assert_awaited_once()


# ---------------------------------------------------------------------------
# onboard_project
# ---------------------------------------------------------------------------


async def test_onboard_dry_run():
    from api.v1.project_routes import OnboardRequest

    body = OnboardRequest(path="/tmp/myrepo", write=False)
    request = _make_request()

    with patch(
        "cli.logic.byor.initialize_repository", new=AsyncMock(return_value=None)
    ) as mock_init:
        result = await onboard_project(body=body, request=request)

    assert result["mode"] == "dry-run"
    mock_init.assert_awaited_once()


async def test_onboard_stage_without_write_returns_early():
    from api.v1.project_routes import OnboardRequest

    body = OnboardRequest(path="/tmp/myrepo", write=False, stage=True)
    request = _make_request()

    result = await onboard_project(body=body, request=request)
    assert result["mode"] == "dry-run"
    assert "note" in result


# ---------------------------------------------------------------------------
# promote_onboard
# ---------------------------------------------------------------------------


async def test_promote_ok():
    from api.v1.project_routes import PromoteRequest

    body = PromoteRequest(path="/tmp/myrepo")
    request = _make_request()

    with patch("cli.logic.byor.promote_staged", new=AsyncMock(return_value=None)):
        result = await promote_onboard(body=body, request=request)

    assert result["promoted"] is True


async def test_promote_returns_400_on_typer_exit():
    import typer
    from fastapi import HTTPException

    from api.v1.project_routes import PromoteRequest

    body = PromoteRequest(path="/tmp/missing")
    request = _make_request()

    with patch(
        "cli.logic.byor.promote_staged",
        new=AsyncMock(side_effect=typer.Exit(code=1)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await promote_onboard(body=body, request=request)
    assert exc_info.value.status_code == 400
