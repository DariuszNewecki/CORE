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

    @staticmethod
    # ID: 5c1d8e2a-9f4b-4a67-b3c8-2d5e6f7a8b9c
    def check_sensitive_route_must_be_gated(tree: ast.AST) -> list[str]:
        """Verify every mutation-verb route in a user-facing module is gated (#770).

        check_router_exposure_enforcement only validates router-CONSTRUCTOR-level
        gates; it has no visibility into per-route decorators, so a newly added
        sensitive endpoint on an already-compliant user-facing router ships
        completely ungated and the existing rule still passes.

        Sensitivity signal: HTTP mutation verb (post/put/delete/patch), reusing
        the read/write axis CORE already applies elsewhere (ActionImpact,
        action_risk.yaml) rather than a new taxonomy. GET/HEAD routes are never
        flagged.

        A route counts as gated if EITHER form already used across this codebase
        is present: `dependencies=[require_governor]` (or `Depends(require_governor)`)
        on the route decorator, or a handler parameter defaulting to
        `require_governor` / `Depends(require_governor)` (the FastAPI DI-parameter
        idiom, e.g. `user: dict = require_governor`).

        Only applies to ROUTER_EXPOSURE='user-facing' modules — governor-only
        modules are already fully gated at the router-constructor level.
        """
        if _find_router_exposure(tree) != "user-facing":
            return []

        findings: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            route_deco = _find_mutation_route_decorator(node)
            if route_deco is None:
                continue
            if _call_has_require_governor(route_deco) or _params_have_require_governor(
                node
            ):
                continue
            findings.append(
                f"'{node.name}' is a {_route_verb(route_deco)!r} route on a "
                "user-facing router with no require_governor gate (neither in "
                "the decorator's dependencies= nor as a handler parameter "
                "default). Add dependencies=[require_governor] to the route "
                "decorator, or a parameter defaulting to require_governor, or "
                "confirm this route is intentionally ungated."
            )
        return findings


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


_MUTATION_VERBS = frozenset({"post", "put", "delete", "patch"})


# ID: 6d2e9f3b-0a5c-4b78-c4d9-3e6f7a8b9c0d
def _find_mutation_route_decorator(
    func: ast.AsyncFunctionDef | ast.FunctionDef,
) -> ast.Call | None:
    """Return the `@<router>.{post,put,delete,patch}(...)` decorator call on
    this function, or None if it has no mutation-verb route decorator."""
    for deco in func.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        func_expr = deco.func
        if isinstance(func_expr, ast.Attribute) and func_expr.attr in _MUTATION_VERBS:
            return deco
    return None


# ID: 7e3f0a4c-1b6d-4c89-d5ea-4f7a8b9c0d1e
def _route_verb(deco: ast.Call) -> str:
    """Return the HTTP verb name from a route decorator call (e.g. 'post')."""
    func_expr = deco.func
    assert isinstance(func_expr, ast.Attribute)
    return func_expr.attr


# ID: 8f4a1b5d-2c7e-4d9a-e6fb-5a8b9c0d1e2f
def _params_have_require_governor(func: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """Return True if any handler parameter defaults to require_governor or
    Depends(require_governor) — the FastAPI DI-parameter gating idiom."""
    for default in func.args.defaults + func.args.kw_defaults:
        if default is None:
            continue
        if isinstance(default, ast.Name) and default.id == "require_governor":
            return True
        if (
            isinstance(default, ast.Call)
            and isinstance(default.func, ast.Name)
            and default.func.id == "Depends"
            and default.args
            and isinstance(default.args[0], ast.Name)
            and default.args[0].id == "require_governor"
        ):
            return True
    return False
