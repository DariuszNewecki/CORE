# tests/api/v1/test_project_routes.py

"""Tests for project routes (capability-docs generation) — mock body deps.

BYOR onboarding routes moved to onboard_routes.py (#782); their tests are in
test_onboard_routes.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi import Response

from api.v1.project_routes import generate_docs


def _make_request(repo_path: str = "/opt/dev/CORE") -> MagicMock:
    req = MagicMock()
    req.app.state.core_context.git_service.repo_path = Path(repo_path)
    return req


def _mock_session() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# generate_docs
# ---------------------------------------------------------------------------


async def test_generate_docs_patches_inner_call():
    """Validate route logic with an injected generator (CapabilityDocsDep)."""
    from api.v1.project_routes import DocsRequest

    body = DocsRequest()
    request = _make_request()
    session = _mock_session()

    mock_main = AsyncMock(return_value=None)
    response = Response()
    result = await generate_docs(
        body=body,
        request=request,
        response=response,
        generate_docs_fn=mock_main,
        session=session,
    )

    assert result == {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}
    mock_main.assert_awaited_once()


async def test_generate_docs_signals_deprecation():
    """ADR-087 D4 (amended 2026-10-03): RFC 9745 Deprecation and RFC 8594
    Sunset headers, and `deprecated: true` in the OpenAPI document."""
    from api.v1.project_routes import DocsRequest, router

    response = Response()
    await generate_docs(
        body=DocsRequest(),
        request=_make_request(),
        response=response,
        generate_docs_fn=AsyncMock(return_value=None),
        session=_mock_session(),
    )
    assert response.headers["Deprecation"] == "@1791028513"
    assert response.headers["Sunset"] == "Sat, 03 Apr 2027 00:00:00 GMT"
    route = next(r for r in router.routes if r.path == "/project/docs")
    assert route.deprecated is True


def test_sunset_does_not_precede_deprecation():
    """RFC 9745: the Sunset time must not precede the Deprecation time."""
    from api.v1.project_routes import DOCS_DEPRECATED_AT, DOCS_SUNSET_AT

    assert DOCS_SUNSET_AT >= DOCS_DEPRECATED_AT


def test_generate_docs_route_carries_governor_gate():
    """#808/#770: generate_docs writes docs/10_CAPABILITY_REFERENCE.md via
    FileHandler -- a real mutation, governor-gated."""
    from api.dependencies import require_governor
    from api.v1.project_routes import router

    gated_by_route = {
        (method, route.path): require_governor in route.dependencies
        for route in router.routes
        for method in route.methods
    }
    assert gated_by_route[("POST", "/project/docs")] is True
