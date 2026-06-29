"""Tests for ApiAuthChecks.check_router_exposure_enforcement (ADR-132 D7)."""

from __future__ import annotations

import ast
import textwrap

from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks


def _parse(src: str) -> ast.AST:
    return ast.parse(textwrap.dedent(src))


# ── happy paths ────────────────────────────────────────────────────────────────

def test_governor_only_with_dependency_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_without_router_dependency_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data")
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_with_per_route_dependency_passes() -> None:
    """require_governor on individual routes is fine for mixed routers."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/mixed")
        admin_router = APIRouter(prefix="/mixed/admin", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_no_router_exposure_skips_file() -> None:
    """Files without ROUTER_EXPOSURE are not API route modules; skip silently."""
    tree = _parse("""
        router = APIRouter(prefix="/stuff", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_depends_wrapped_require_governor_passes() -> None:
    """Accepts both bare require_governor and Depends(require_governor) in dependencies."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[Depends(require_governor)])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


# ── violations ────────────────────────────────────────────────────────────────

def test_governor_only_missing_dependency_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]
    assert "require_governor" in violations[0]


def test_governor_only_wrong_dependency_is_violation() -> None:
    """A different dependency in the list is not a substitute for require_governor."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[get_current_user])
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]


def test_user_facing_with_router_level_dependency_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data", dependencies=[require_governor])
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "user-facing" in violations[0]
    assert "require_governor" in violations[0]


def test_unknown_exposure_value_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "internal"
        router = APIRouter(prefix="/x")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "unrecognised" in violations[0]
    assert "internal" in violations[0]
