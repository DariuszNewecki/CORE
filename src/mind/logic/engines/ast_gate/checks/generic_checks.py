# src/mind/logic/engines/ast_gate/checks/generic_checks.py
"""
Universal AST Primitives - Enhanced for Forbidden and Mandatory Patterns.

CONSTITUTIONAL FIX:
- Added 'required_calls' primitive to support mandatory instrumentation rules.
- Enables 'autonomy.tracing.mandatory' to verify presence rather than absence.
- Maintains 'dry_by_design' by centralizing call-graph inspection.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: cf804085-ee18-4126-a16b-7b447793f3f9
class GenericASTChecks:
    @staticmethod
    # ID: d44dcc3a-7ca0-4448-8f5e-19c28567d53c
    def is_selected(node: ast.AST, selector: dict[str, Any]) -> bool:
        """Determines if a rule applies to this specific node."""
        if not selector:
            return True

        if "has_decorator" in selector:
            target = selector["has_decorator"]
            for dec in getattr(node, "decorator_list", []):
                name = ASTHelpers.full_attr_name(
                    dec.func if isinstance(dec, ast.Call) else dec
                )
                if name == target:
                    return True
            return False

        if "name_regex" in selector:
            return bool(re.search(selector["name_regex"], getattr(node, "name", "")))

        return True

    @staticmethod
    # ID: b99005fa-8eba-4564-b70f-f37aa630ed9a
    def validate_requirement(node: ast.AST, requirement: dict[str, Any]) -> str | None:
        """Checks if the node meets the requirement. Returns error string or None."""
        check_type = requirement.get("check_type")

        # 1. Primitive: returns_type (e.g. must return ActionResult)
        if check_type == "returns_type":
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return None
            actual = ASTHelpers.full_attr_name(node.returns) if node.returns else "None"
            if actual != requirement.get("expected"):
                return (
                    f"expected '-> {requirement.get('expected')}', found '-> {actual}'"
                )

        # 2. Primitive: forbidden_calls (e.g. no print() or input())
        if check_type == "forbidden_calls":
            forbidden = set(requirement.get("calls", []))
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Call):
                    name = ASTHelpers.full_attr_name(sub_node.func)
                    if name in forbidden:
                        return f"contains forbidden call '{name}()' on line {sub_node.lineno}"

        # 3. CONSTITUTIONAL FIX: required_calls (e.g. MUST call self.tracer.record())
        # This replaces the backward 'forbidden_calls' logic used in tracing.
        if check_type == "required_calls":
            required = set(requirement.get("calls", []))
            found_calls = set()

            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Call):
                    name = ASTHelpers.full_attr_name(sub_node.func)
                    if name:
                        found_calls.add(name)

            missing = sorted(list(required - found_calls))
            if missing:
                return f"missing mandatory call(s): {missing}"

        # 4. Primitive: forbidden_imports (e.g. no 'rich' or 'click')
        if check_type == "forbidden_imports":
            forbidden = set(requirement.get("imports", []))
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Import):
                    for alias in sub_node.names:
                        if alias.name.split(".")[0] in forbidden:
                            return f"contains forbidden import '{alias.name}'"
                if isinstance(sub_node, ast.ImportFrom) and sub_node.module:
                    if sub_node.module.split(".")[0] in forbidden:
                        return f"contains forbidden import-from '{sub_node.module}'"

        # 5. Primitive: decorator_args (e.g. @atomic_action must have action_id)
        if check_type == "decorator_args":
            target_dec = requirement.get("decorator")
            required_keys = set(requirement.get("required_kwargs", []))
            for dec in getattr(node, "decorator_list", []):
                name = ASTHelpers.full_attr_name(
                    dec.func if isinstance(dec, ast.Call) else dec
                )
                if name == target_dec:
                    present_keys = (
                        {kw.arg for kw in dec.keywords}
                        if isinstance(dec, ast.Call)
                        else set()
                    )
                    missing = sorted(list(required_keys - present_keys))
                    if missing:
                        return f"decorator @{target_dec} missing arguments: {missing}"

        return None
