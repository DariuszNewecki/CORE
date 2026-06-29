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
        - ROUTER_EXPOSURE='governor-only' → APIRouter constructor MUST carry
          require_governor in its dependencies list.
        - ROUTER_EXPOSURE='user-facing' → APIRouter constructor MUST NOT carry
          require_governor in its router-level dependencies (per-route gates are fine).

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

        router_has_gate = _router_constructor_has_require_governor(tree)

        if exposure == "governor-only" and not router_has_gate:
            return [
                "ROUTER_EXPOSURE='governor-only' but APIRouter constructor lacks "
                "require_governor in its dependencies list. "
                "Add: router = APIRouter(..., dependencies=[require_governor])"
            ]

        if exposure == "user-facing" and router_has_gate:
            return [
                "ROUTER_EXPOSURE='user-facing' but APIRouter constructor carries "
                "require_governor in its router-level dependencies. "
                "Remove it from the APIRouter constructor; per-route gates are fine."
            ]

        return []


# ID: f89a11d0-f923-42bc-bf2b-f31824b37008
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


# ID: 16f3b196-720c-4ac6-ac0f-2beade1c1629
def _router_constructor_has_require_governor(tree: ast.AST) -> bool:
    """Return True if the main router's APIRouter() call lists require_governor in dependencies."""
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "router"
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
