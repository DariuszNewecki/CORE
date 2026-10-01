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
