# tests/api/v1/test_role_enforcement.py

"""Role enforcement integration tests for mutation endpoints.

Uses TestClient so that FastAPI's dependency-injection machinery fires —
direct handler calls bypass `dependencies=[...]` decorators entirely.

Strategy: override `get_current_user` to inject a controlled user dict;
test wrong-role → 403 for every protected mutation endpoint. Happy-path
handler behavior is already covered in the per-route unit test files.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.v1.daemon_routes import router as daemon_router
from api.v1.fix_routes import router as fix_router
from api.v1.proposals_routes import router as proposals_router


_VIEWER = {"sub": "uid-v", "email": "viewer@example.com", "role": "viewer", "org_id": "o"}


def _app_with_role(role: str) -> FastAPI:
    """Minimal FastAPI app with all three routers; get_current_user returns role."""
    user = {"sub": "uid-1", "email": "user@example.com", "role": role, "org_id": "o"}
    app = FastAPI()
    app.include_router(fix_router)
    app.include_router(proposals_router)
    app.include_router(daemon_router)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.mark.parametrize(
    "method,path,body",
    [
        # fix_routes — mutation endpoints
        ("POST", "/fix/run/fix.format", None),
        ("POST", "/fix/all", None),
        ("POST", "/fix/modularity", None),
        # proposals_routes — mutation endpoints
        (
            "POST",
            "/proposals/p-1/approve",
            {"approved_by": "x", "approval_authority": "governor_direct"},
        ),
        ("POST", "/proposals/p-1/execute", None),
        # daemon_routes — all endpoints (router-level dependency)
        ("GET", "/daemon/status", None),
        ("POST", "/daemon/start", None),
        ("POST", "/daemon/stop", None),
    ],
)
def test_mutation_endpoint_rejects_non_admin(method: str, path: str, body: dict | None) -> None:
    """Non-platform_admin role receives 403 on every protected mutation endpoint."""
    client = TestClient(_app_with_role("viewer"), raise_server_exceptions=False)
    response = client.request(method, path, json=body or {})
    assert response.status_code == 403, (
        f"{method} {path} returned {response.status_code}, expected 403"
    )


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/fix/run/fix.format", None),
        ("POST", "/fix/all", None),
        ("POST", "/fix/modularity", None),
        (
            "POST",
            "/proposals/p-1/approve",
            {"approved_by": "x", "approval_authority": "governor_direct"},
        ),
        ("POST", "/proposals/p-1/execute", None),
        ("GET", "/daemon/status", None),
        ("POST", "/daemon/start", None),
        ("POST", "/daemon/stop", None),
    ],
)
def test_mutation_endpoint_passes_role_check_for_platform_admin(
    method: str, path: str, body: dict | None
) -> None:
    """platform_admin role passes the role gate — the request reaches the handler.

    The handler body may return any status except 403 (it will typically
    fail with 422/500 in this minimal test app which has no DB or
    core_context). A non-403 response confirms the role check succeeded.
    """
    client = TestClient(_app_with_role("platform_admin"), raise_server_exceptions=False)
    response = client.request(method, path, json=body or {})
    assert response.status_code != 403, (
        f"{method} {path} returned 403 for platform_admin — role check is blocking admins"
    )
