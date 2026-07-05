"""Tests for ApiAuthChecks — router_exposure_enforcement and route_module_must_declare_exposure (ADR-132 D7)."""

from __future__ import annotations

import ast
import textwrap

from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks


def _parse(src: str) -> ast.AST:
    return ast.parse(textwrap.dedent(src))


# ── happy paths — single router ───────────────────────────────────────────────


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


def test_user_facing_with_secondary_router_gate_passes() -> None:
    """Secondary router with require_governor is fine in a user-facing file.

    Being more restrictive than the file tier is allowed. The checker only
    constrains the primary 'router' variable for user-facing files.
    """
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


def test_governor_only_multiple_routers_all_gated_passes() -> None:
    """Every APIRouter in a governor-only file carries the gate — no violation."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
        admin_router = APIRouter(prefix="/admin", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_multiple_routers_none_gated_passes() -> None:
    """Multiple ungated routers in a user-facing file — no violation."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/fix")
        actions_router = APIRouter()
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


# ── violations — single router ────────────────────────────────────────────────


def test_governor_only_missing_dependency_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]
    assert "require_governor" in violations[0]
    assert "'router'" in violations[0]


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


# ── violations — multiple routers (the previously blind case) ─────────────────


def test_governor_only_secondary_router_missing_gate_is_violation() -> None:
    """Secondary router without require_governor in a governor-only file is a violation.

    Previously the checker only inspected 'router' and would have missed
    'ops_router' entirely.
    """
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/admin", dependencies=[require_governor])
        ops_router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]
    assert "'ops_router'" in violations[0]


def test_governor_only_both_routers_missing_gate_reports_both() -> None:
    """Every ungated router in a governor-only file produces its own finding."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/admin")
        ops_router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 2
    names_in_findings = " ".join(violations)
    assert "'ops_router'" in names_in_findings
    assert "'router'" in names_in_findings


# ── route_module_must_declare_exposure ────────────────────────────────────────


def test_exposure_declared_passes() -> None:
    """Any file with ROUTER_EXPOSURE present passes the completeness check."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_route_module_must_declare_exposure(tree) == []


def test_user_facing_exposure_declared_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data")
    """)
    assert ApiAuthChecks.check_route_module_must_declare_exposure(tree) == []


def test_missing_exposure_is_violation() -> None:
    """A route module with no ROUTER_EXPOSURE declaration fires the rule."""
    tree = _parse("""
        router = APIRouter(prefix="/ungoverned")
    """)
    violations = ApiAuthChecks.check_route_module_must_declare_exposure(tree)
    assert len(violations) == 1
    assert "ROUTER_EXPOSURE" in violations[0]


def test_empty_module_is_violation() -> None:
    """An entirely empty route module has no ROUTER_EXPOSURE."""
    tree = _parse("")
    violations = ApiAuthChecks.check_route_module_must_declare_exposure(tree)
    assert len(violations) == 1
