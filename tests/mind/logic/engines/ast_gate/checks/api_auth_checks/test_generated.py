from __future__ import annotations

import ast
from unittest.mock import patch


# ID: 938d587e-4a93-48b5-b038-5513ae89bbd2
def test_ApiAuthChecks():
    from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks

    # A user-facing module with a plain primary router and a gated GET route
    # should be fully compliant on all three checks.
    source = (
        "ROUTER_EXPOSURE = 'user-facing'\n"
        "router = APIRouter()\n"
        "\n"
        "@router.get('/items')\n"
        "async def list_items():\n"
        "    return []\n"
    )
    tree = ast.parse(source)

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.api_auth_checks._find_router_exposure",
            return_value="user-facing",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.api_auth_checks._find_all_router_gates",
            return_value={"router": False},
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.api_auth_checks._find_intentionally_ungated",
            return_value={},
        ),
    ):
        assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []
        assert ApiAuthChecks.check_route_module_must_declare_exposure(tree) == []
        assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


import mind.logic.engines.ast_gate.checks.api_auth_checks as api_auth_checks
from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks


# ID: f5c5231a-999c-41bc-9d87-fab129fae109
def test_ApiAuthChecks_check_sensitive_route_must_be_gated() -> None:
    check_sensitive_route_must_be_gated = getattr(
        api_auth_checks, "check_sensitive_route_must_be_gated", None
    )
    if check_sensitive_route_must_be_gated is None:
        import pytest

        pytest.skip("check_sensitive_route_must_be_gated not available")

    source = (
        "from fastapi import APIRouter, Depends\n"
        "from x import require_governor\n"
        "ROUTER_EXPOSURE = 'user-facing'\n"
        "router = APIRouter()\n"
        "\n"
        "@router.post('/ungated')\n"
        "async def ungated_route():\n"
        "    return {}\n"
        "\n"
        "@router.post('/gated', dependencies=[require_governor])\n"
        "async def gated_route():\n"
        "    return {}\n"
    )
    tree = ast.parse(source)

    findings = check_sensitive_route_must_be_gated(tree)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "ungated_route" in findings[0]
    assert "require_governor" in findings[0]


# ID: 2410bc69-68a1-4d33-aa66-858a05b47d4b
def test_ApiAuthChecks_check_router_exposure_enforcement() -> None:
    source = "from fastapi import APIRouter\nrouter = APIRouter()\nROUTER_EXPOSURE = 'user-facing'\n"
    tree = ast.parse(source)
    result = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert result == []


# ID: 646356cc-1978-4ce1-a33b-2267d6b884a3
def test_check_route_module_must_declare_exposure() -> None:
    source = "ROUTER_EXPOSURE = 'user-facing'\n"
    tree = ast.parse(source)

    with patch(
        "mind.logic.engines.ast_gate.checks.api_auth_checks._find_router_exposure",
        return_value=ast.Constant(value="user-facing"),
    ) as mock_find:
        result = ApiAuthChecks.check_route_module_must_declare_exposure(tree)

    assert result == []
    mock_find.assert_called_once_with(tree)


# ID: 8926317a-838c-4b55-8233-0826de08bc5b
def test_ApiAuthChecks_check_route_module_must_declare_exposure() -> None:
    check_fn = getattr(api_auth_checks, "ApiAuthChecks", None)
    # The symbol is exposed as a module-level function; fall back to module attr lookup.
    func = getattr(api_auth_checks, "check_route_module_must_declare_exposure", None)
    if func is None:
        if check_fn is not None:
            func = getattr(check_fn, "check_route_module_must_declare_exposure")
        else:
            raise AssertionError(
                "check_route_module_must_declare_exposure not found in module"
            )

    tree = ast.parse("ROUTER_EXPOSURE = 'user-facing'\n")

    with patch.object(
        api_auth_checks,
        "_find_router_exposure",
        return_value=ast.Constant(value="user-facing"),
    ) as mock_find:
        result = func(tree)

    mock_find.assert_called_once_with(tree)
    assert result == []
