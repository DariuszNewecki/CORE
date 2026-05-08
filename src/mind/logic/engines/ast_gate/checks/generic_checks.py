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


_NESTED_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_COMPOUND_STMTS = (
    ast.If,
    ast.For,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncFor,
    ast.AsyncWith,
)


def _iter_sub_bodies(stmt: ast.AST):
    """Yield the sub-statement lists of a compound statement in source order."""
    if isinstance(stmt, ast.If):
        yield stmt.body
        yield stmt.orelse
    elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        yield stmt.body
        yield stmt.orelse
    elif isinstance(stmt, ast.Try):
        yield stmt.body
        for handler in stmt.handlers:
            yield handler.body
        yield stmt.orelse
        yield stmt.finalbody
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        yield stmt.body


def _has_explicit_return(stmts: list[ast.stmt]) -> bool:
    """True if any ast.Return appears in stmts, recursing into compound
    statements but NOT into nested function/class definitions."""
    for stmt in stmts:
        if isinstance(stmt, _NESTED_DEFS):
            continue
        if isinstance(stmt, ast.Return):
            return True
        if isinstance(stmt, _COMPOUND_STMTS):
            for sub_body in _iter_sub_bodies(stmt):
                if _has_explicit_return(sub_body):
                    return True
    return False


def _stmts_missing_calls(
    stmts: list[ast.stmt],
    required: set[str],
    seen: set[str],
    _is_top: bool = True,
) -> set[str]:
    """Path-sensitive walk over stmts. Returns the set of required calls
    missing on at least one function-exit path reachable from this point.

    `seen` is the set of required calls already observed on the path
    leading into stmts. Calls discovered inside a compound's sub-body are
    NOT propagated back to the parent's `seen` because the sub-body may
    not execute (an `if` branch, an empty loop, an unraised exception).

    `_is_top` is True only at the function-body root: end-of-stmts there
    is the implicit `return None` (a real function exit) and contributes
    `required - seen` to the missing set. For sub-body recursion
    (`_is_top=False`), end-of-stmts means control flows past the compound
    back to the parent — not a function exit — so the empty set is
    returned and the parent continues with its own `seen` unchanged.
    """
    seen = set(seen)
    for stmt in stmts:
        if isinstance(stmt, _NESTED_DEFS):
            continue
        if isinstance(stmt, ast.Return):
            return required - seen
        if isinstance(stmt, _COMPOUND_STMTS):
            sub_missing: set[str] = set()
            for sub_body in _iter_sub_bodies(stmt):
                sub_missing |= _stmts_missing_calls(
                    sub_body, required, seen, _is_top=False
                )
            if sub_missing:
                return sub_missing
        else:
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, ast.Call):
                    name = ASTHelpers.full_attr_name(sub_node.func)
                    if name in required:
                        seen.add(name)
    if _is_top:
        return required - seen
    return set()


def _check_required_calls_coverage(node: ast.AST, required_calls: set[str]) -> set[str]:
    """Path-sensitive coverage check for required calls.

    When `node` has no explicit return statements anywhere in its body
    (excluding nested defs), the function has only one exit (implicit
    fall-through), so existence on any line implies coverage and we
    fall back to ast.walk over the whole node — preserving prior
    semantics for that class of function.

    Otherwise, walks `node.body` in execution order and returns the set
    of required calls missing on at least one function-exit path.
    """
    body = getattr(node, "body", [])
    if not _has_explicit_return(body):
        found: set[str] = set()
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Call):
                name = ASTHelpers.full_attr_name(sub_node.func)
                if name:
                    found.add(name)
        return required_calls - found
    return _stmts_missing_calls(body, required_calls, set())


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
            # getattr returns None when the attribute exists but is None
            # (ast.ExceptHandler without "as" binding, ast.MatchStar/MatchAs
            # without binding). ast.TypeAlias.name is an ast.Name node, not
            # a string. Coerce both cases to a safe empty-string fallback
            # so the regex never sees a non-string value.
            name = getattr(node, "name", "") or ""
            if not isinstance(name, str):
                return False
            return bool(re.search(selector["name_regex"], name))

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

        # 3. required_calls — path-sensitive when the function has explicit
        # returns; falls back to existence-only ast.walk for fall-through-only
        # bodies (one exit, so existence equals coverage).
        if check_type == "required_calls":
            required = set(requirement.get("calls", []))
            body = getattr(node, "body", [])
            missing_set = _check_required_calls_coverage(node, required)
            if missing_set:
                missing = sorted(missing_set)
                if _has_explicit_return(body):
                    return f"missing mandatory call(s) on some return path: {missing}"
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
