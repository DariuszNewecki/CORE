# tests/api/v1/test_project_routes.py

"""Tests for project routes (capability-docs generation) — mock body deps.

BYOR onboarding routes moved to onboard_routes.py (#782); their tests are in
test_onboard_routes.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Validate route logic by patching the lazy body import."""
    from api.v1.project_routes import DocsRequest

    body = DocsRequest()
    request = _make_request()
    session = _mock_session()

    with patch(
        "body.introspection.generate_capability_docs.main",
        new=AsyncMock(return_value=None),
    ) as mock_main:
        # Call the route: it imports main lazily and calls it
        result = await generate_docs(body=body, request=request, session=session)

    assert result == {"output": "docs/10_CAPABILITY_REFERENCE.md", "generated": True}
    mock_main.assert_awaited_once()


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
