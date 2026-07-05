# src/mind/logic/engines/ast_gate/checks/api_auth_checks.py
"""API authentication boundary checks (ADR-132 D7)."""

from __future__ import annotations

import ast


# ID: ac64bdfa-2c71-4c06-9cdc-cdcf2d30f474
class ApiAuthChecks:
    """Enforce agreement between ROUTER_EXPOSURE and APIRouter dependencies."""

    @staticmethod
    # ID: b62dd0c5-51c1-414c-a14f-7b4d2296c46e
    def check_router_exposure_enforcement(tree: ast.AST) -> list[str]:
        """Verify ROUTER_EXPOSURE and router-level require_governor agree (ADR-132 D7).

        Rules:
        - ROUTER_EXPOSURE='governor-only' → every APIRouter() assignment in the
          file MUST carry require_governor in its constructor dependencies. A
          secondary router without the gate is as much a violation as the primary
          one — the checker was previously blind to non-'router' variables.
        - ROUTER_EXPOSURE='user-facing' → the primary APIRouter (named 'router')
          MUST NOT carry require_governor at the constructor level. Secondary
          routers MAY carry it (being more restrictive than the file tier is fine;
          per-route gates on individual endpoints are always fine).

        Returns an empty list for files that declare no ROUTER_EXPOSURE (not a
        route module; the rule scope limits calls to src/api/v1/**/*.py).
        """
        exposure = _find_router_exposure(tree)
        if exposure is None:
            return []

        if exposure not in ("governor-only", "user-facing"):
            return [
                f"ROUTER_EXPOSURE has unrecognised value {exposure!r}; "
                f"expected 'governor-only' or 'user-facing'"
            ]

        all_gates = _find_all_router_gates(tree)

        findings: list[str] = []

        if exposure == "governor-only":
            for name in sorted(all_gates):
                if not all_gates[name]:
                    findings.append(
                        f"ROUTER_EXPOSURE='governor-only' but APIRouter '{name}' "
                        "constructor lacks require_governor in its dependencies list. "
                        f"Add: {name} = APIRouter(..., dependencies=[require_governor])"
                    )
        else:  # user-facing
            # Only the primary router is constrained — secondary routers may be
            # more restrictive (constructor gate present) without it being a violation.
            if all_gates.get("router", False):
                findings.append(
                    "ROUTER_EXPOSURE='user-facing' but APIRouter 'router' constructor "
                    "carries require_governor in its router-level dependencies. "
                    "Remove it from the APIRouter constructor; per-route gates are fine."
                )

        return findings

    @staticmethod
    # ID: 849f8d07-2a31-4b93-a6d6-7835b109158f
    def check_route_module_must_declare_exposure(tree: ast.AST) -> list[str]:
        """Verify every *_routes.py module declares ROUTER_EXPOSURE (ADR-132 completeness).

        Fires when ROUTER_EXPOSURE is absent entirely. The consistency rule
        (check_router_exposure_enforcement) handles the case where it IS present
        but inconsistent with the router dependencies.
        """
        if _find_router_exposure(tree) is None:
            return [
                "Route module missing ROUTER_EXPOSURE declaration. "
                "Add: ROUTER_EXPOSURE = 'governor-only'  or  ROUTER_EXPOSURE = 'user-facing'"
            ]
        return []


# ID: a906415b-311a-42d5-8df8-8a8db0b856fe
def _find_router_exposure(tree: ast.AST) -> str | None:
    """Return the string value of ROUTER_EXPOSURE if declared, else None."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "ROUTER_EXPOSURE"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


# ID: 793f2ded-04ad-4710-a813-76ff72f339be
def _find_all_router_gates(tree: ast.AST) -> dict[str, bool]:
    """Return {var_name: has_require_governor} for every APIRouter() assignment in the module.

    Covers all simple assignments of the form `name = APIRouter(...)`, regardless
    of the variable name. Previously only 'router' was checked, leaving secondary
    routers (e.g. 'actions_router', 'admin_router') invisible to the checker.
    """
    result: dict[str, bool] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            continue
        call = node.value
        func = call.func
        is_api_router = (isinstance(func, ast.Name) and func.id == "APIRouter") or (
            isinstance(func, ast.Attribute) and func.attr == "APIRouter"
        )
        if not is_api_router:
            continue
        result[node.targets[0].id] = _call_has_require_governor(call)
    return result


# ID: de091033-f205-4114-b6f3-3aa101da4312
def _call_has_require_governor(call: ast.Call) -> bool:
    """Return True if an APIRouter() call lists require_governor in its dependencies."""
    for kw in call.keywords:
        if kw.arg != "dependencies":
            continue
        if not isinstance(kw.value, ast.List):
            continue
        for elt in kw.value.elts:
            if isinstance(elt, ast.Name) and elt.id == "require_governor":
                return True
            if (
                isinstance(elt, ast.Call)
                and isinstance(elt.func, ast.Name)
                and elt.func.id == "Depends"
                and elt.args
                and isinstance(elt.args[0], ast.Name)
                and elt.args[0].id == "require_governor"
            ):
                return True
    return False
