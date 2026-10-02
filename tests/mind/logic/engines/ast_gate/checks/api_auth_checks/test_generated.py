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


from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks


# ID: 048df3c7-bd85-4496-b8ce-6bc24bfc7231
def test_check_route_module_must_declare_exposure() -> None:
    source = "ROUTER_EXPOSURE = 'governor-only'\n"
    tree = ast.parse(source)

    with patch(
        "mind.logic.engines.ast_gate.checks.api_auth_checks._find_router_exposure",
        return_value=ast.Constant(value="governor-only"),
    ):
        result = ApiAuthChecks.check_route_module_must_declare_exposure(tree)

    assert result == []


import mind.logic.engines.ast_gate.checks.api_auth_checks as api_auth_checks


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





# ID: aaf792ac-e418-47b8-9634-042ab5db5400
def test_check_route_module_must_declare_exposure() -> None:
    source = "ROUTER_EXPOSURE = 'user-facing'\n"
    tree = ast.parse(source)
    with patch(
        "mind.logic.engines.ast_gate.checks.api_auth_checks._find_router_exposure",
        return_value=object(),
    ):
        result = ApiAuthChecks.check_route_module_must_declare_exposure(tree)
    assert result == []
