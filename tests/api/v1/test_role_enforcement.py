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
from api.v1.auth_routes import router as auth_router
from api.v1.daemon_routes import router as daemon_router
from api.v1.development_routes import router as development_router
from api.v1.fix_routes import router as fix_router
from api.v1.integrity_routes import router as integrity_router
from api.v1.proposals_routes import router as proposals_router
from api.v1.refactor_routes import router as refactor_router
from api.v1.sync_routes import router as sync_router


_VIEWER = {
    "sub": "uid-v",
    "email": "viewer@example.com",
    "role": "viewer",
    "org_id": "o",
}


def _app_with_role(role: str) -> FastAPI:
    """Minimal FastAPI app with all governor-gated routers; get_current_user returns role."""
    user = {"sub": "uid-1", "email": "user@example.com", "role": role, "org_id": "o"}
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(fix_router)
    app.include_router(proposals_router)
    app.include_router(daemon_router)
    app.include_router(development_router)
    app.include_router(integrity_router)
    app.include_router(refactor_router)
    app.include_router(sync_router)
    app.dependency_overrides[get_current_user] = lambda: user
    from api.v1.auth_routes import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: None
    return app


# ── Governor gate: non-admin → 403 ────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path,body",
    [
        # auth_routes — per-route governor gates (ADR-132 alignment)
        ("POST", "/auth/users/uid-x/suspend", None),
        ("POST", "/auth/users/uid-x/reactivate", None),
        # fix_routes — per-route governor gates
        ("POST", "/fix/run/fix.format", None),
        ("POST", "/fix/all", None),
        ("POST", "/fix/modularity", None),
        # proposals_routes — per-route governor gates
        ("POST", "/proposals/p-1/approve", {"approval_authority": "governor_direct"}),
        ("POST", "/proposals/p-1/execute", None),
        # daemon_routes — router-level gate
        ("GET", "/daemon/status", None),
        ("POST", "/daemon/start", None),
        ("POST", "/daemon/stop", None),
        # development_routes — router-level gate (ADR-132 D3)
        ("POST", "/develop/goal", {"goal": "x", "workflow_type": "y", "write": False}),
        # integrity_routes — router-level gate (ADR-132 D3)
        ("POST", "/integrity/baseline", None),
        ("POST", "/integrity/verify", None),
        # refactor_routes — router-level gate (ADR-132 D3)
        ("GET", "/refactor/score", None),
        ("GET", "/refactor/runs/00000000-0000-0000-0000-000000000001", None),
        # sync_routes — router-level gate (ADR-132 D3)
        ("POST", "/sync/knowledge-graph", None),
        ("GET", "/sync/runs/00000000-0000-0000-0000-000000000001", None),
    ],
)
def test_mutation_endpoint_rejects_non_admin(
    method: str, path: str, body: dict | None
) -> None:
    """Non-platform_admin role receives 403 on every governor-gated endpoint."""
    client = TestClient(_app_with_role("viewer"), raise_server_exceptions=False)
    response = client.request(method, path, json=body or {})
    assert response.status_code == 403, (
        f"{method} {path} returned {response.status_code}, expected 403"
    )


# ── Governor gate: platform_admin passes ──────────────────────────────────────


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/auth/users/uid-x/suspend", None),
        ("POST", "/auth/users/uid-x/reactivate", None),
        ("POST", "/fix/run/fix.format", None),
        ("POST", "/fix/all", None),
        ("POST", "/fix/modularity", None),
        ("POST", "/proposals/p-1/approve", {"approval_authority": "governor_direct"}),
        ("POST", "/proposals/p-1/execute", None),
        ("GET", "/daemon/status", None),
        ("POST", "/daemon/start", None),
        ("POST", "/daemon/stop", None),
        ("POST", "/develop/goal", {"goal": "x", "workflow_type": "y", "write": False}),
        ("POST", "/integrity/baseline", None),
        ("POST", "/integrity/verify", None),
        ("GET", "/refactor/score", None),
        ("POST", "/sync/knowledge-graph", None),
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


# ── Canonical sentinel: require_governor is the single definition ─────────────


# ID: a3d8f1b5-2e7c-4b9d-8f0a-5c4e1d6a3b27
def test_require_governor_is_canonical_platform_admin_gate() -> None:
    """require_governor must be the only place 'platform_admin' is hardcoded (ADR-132 D2)."""
    import ast
    import pathlib

    api_root = pathlib.Path(__file__).parents[3] / "src" / "api"
    violations: list[str] = []

    # auth_routes.py: invite handler legitimately checks platform_admin inline
    # because org_admin is also a valid caller (multi-role path, not DI-expressible).
    # suspend/reactivate have been migrated to require_governor (ADR-132 D2).
    _EXCLUDED = {"dependencies.py", "auth_routes.py"}

    for py_file in api_root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        if py_file.name in _EXCLUDED:
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "platform_admin":
                violations.append(f"{py_file.relative_to(api_root)}:{node.lineno}")

    assert not violations, (
        "Hardcoded 'platform_admin' string outside dependencies.py — "
        "use require_governor instead (ADR-132 D2):\n" + "\n".join(violations)
    )
