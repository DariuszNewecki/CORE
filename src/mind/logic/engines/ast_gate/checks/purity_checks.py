# src/mind/logic/engines/ast_gate/checks/purity_checks.py
"""
Purity Checks - Deterministic AST-based enforcement.

Focused on rules from .intent/policies/code/purity.json and adjacent purity constraints.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: 6b2a85b5-2b76-4db7-bfb4-4f3a8b7b5f11
class PurityChecks:
    """
    Stateless check collection for the AST gate engine.
    Each check returns a list[str] of human-readable violations.
    """

    # ID: 9b3f3c34-2bba-4cf1-9d8b-51d548a61b7e
    _ID_ANCHOR_PREFIXES: ClassVar[tuple[str, ...]] = ("# ID:",)

    @staticmethod
    # ID: 7b2f0a5a-cf7d-4af4-9b3c-7bbd7b4d36d4
    def check_stable_id_anchor(source: str) -> list[str]:
        """
        Ensures that the file contains at least one stable ID anchor.
        This is intentionally simple: many other tools rely on '# ID:' anchors.
        """
        lines = source.splitlines()
        for line in lines[:200]:  # cheap bound; IDs should be near top or near symbols
            stripped = line.strip()
            if any(stripped.startswith(p) for p in PurityChecks._ID_ANCHOR_PREFIXES):
                return []
        return ["Missing stable ID anchor: expected at least one '# ID: <...>' line."]

    @staticmethod
    # ID: 1cc2a7f3-5e21-4c10-9f93-5d2b7bdb3a65
    def check_forbidden_decorators(tree: ast.AST, forbidden: list[str]) -> list[str]:
        violations: list[str] = []
        forbidden_set = {
            d.strip() for d in forbidden if isinstance(d, str) and d.strip()
        }
        if not forbidden_set:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for dec in node.decorator_list:
                dec_name = ASTHelpers.full_attr_name(dec)
                if dec_name in forbidden_set:
                    violations.append(
                        f"Forbidden decorator '{dec_name}' on function '{node.name}' (line {ASTHelpers.lineno(dec)})."
                    )
                # Also catch calls like @x.y(...)
                if isinstance(dec, ast.Call):
                    call_name = ASTHelpers.full_attr_name(dec.func)
                    if call_name in forbidden_set:
                        violations.append(
                            f"Forbidden decorator '{call_name}' on function '{node.name}' (line {ASTHelpers.lineno(dec)})."
                        )

        return violations

    @staticmethod
    # ID: 432da7b5-4aa2-4557-9c56-9c0ce540a23d
    def check_forbidden_primitives(tree: ast.AST, forbidden: list[str]) -> list[str]:
        violations: list[str] = []
        forbidden_set = {
            p.strip() for p in forbidden if isinstance(p, str) and p.strip()
        }
        if not forbidden_set:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_set:
                violations.append(
                    f"Forbidden primitive '{node.id}' used (line {ASTHelpers.lineno(node)})."
                )
            elif isinstance(node, ast.Attribute):
                name = ASTHelpers.full_attr_name(node)
                if name and name in forbidden_set:
                    violations.append(
                        f"Forbidden primitive '{name}' used (line {ASTHelpers.lineno(node)})."
                    )

        return violations

    @staticmethod
    # ID: 3e2f4d95-02db-4f55-9fdb-9e55f9a9d918
    def check_no_print_statements(tree: ast.AST) -> list[str]:
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = ASTHelpers.full_attr_name(node.func)
                if call_name == "print":
                    violations.append(
                        f"Disallowed print() call (line {ASTHelpers.lineno(node)})."
                    )
        return violations

    @staticmethod
    # ID: 2dd7a4b8-fc4e-468e-9a1a-315acb2b3d6f
    def check_decorator_args(
        tree: ast.AST, decorator: str, required_args: list[str]
    ) -> list[str]:
        """
        Enforces that @<decorator>(...) includes all required keyword args.

        Example policy:
            check_type: decorator_args
            decorator: atomic_action
            required_args: ["action_id", "impact", "policies"]
        """
        violations: list[str] = []
        required = [
            a.strip() for a in required_args if isinstance(a, str) and a.strip()
        ]
        required_set = set(required)
        if not required_set:
            return violations

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Find the decorator occurrence(s)
            for dec in fn.decorator_list:
                # @atomic_action  (no call) -> violation because args cannot exist
                if isinstance(dec, ast.Name) and dec.id == decorator:
                    violations.append(
                        f"@{decorator} on '{fn.name}' must be called with arguments "
                        f"{sorted(required_set)} (line {ASTHelpers.lineno(dec)})."
                    )
                    continue

                # @x.atomic_action  (no call)
                if (
                    isinstance(dec, ast.Attribute)
                    and ASTHelpers.full_attr_name(dec) == decorator
                ):
                    violations.append(
                        f"@{decorator} on '{fn.name}' must be called with arguments "
                        f"{sorted(required_set)} (line {ASTHelpers.lineno(dec)})."
                    )
                    continue

                # @atomic_action(...)
                if isinstance(dec, ast.Call):
                    call_name = ASTHelpers.full_attr_name(dec.func)
                    if (
                        call_name != decorator
                        and (call_name or "").split(".")[-1] != decorator
                    ):
                        continue

                    # Collect keyword arg names actually present
                    present_kw = {kw.arg for kw in dec.keywords if kw.arg}
                    missing = sorted(list(required_set - present_kw))

                    if missing:
                        violations.append(
                            f"@{decorator} on '{fn.name}' missing required args {missing} "
                            f"(line {ASTHelpers.lineno(dec)})."
                        )

        return violations

    @staticmethod
    # ID: 9f2f6b65-9ff0-4b7b-9b2e-8e2c22f2f50c
    def check_required_decorator(
        tree: ast.AST,
        decorator: str,
        only_public: bool = True,
        ignore_tests: bool = True,
    ) -> list[str]:
        """
        Conservative enforcement:
        - Applies to public functions by default (name does not start with '_')
        - Ignores tests by default (function names starting with 'test_' are skipped)
        - Uses a heuristic to decide "state modifying":
            * assignment to self.<attr>
            * calls that look like writes / commits / executes / deletes
        """
        violations: list[str] = []

        def _has_decorator(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
            for dec in fn.decorator_list:
                if isinstance(dec, ast.Call):
                    name = ASTHelpers.full_attr_name(dec.func) or ""
                else:
                    name = ASTHelpers.full_attr_name(dec) or ""
                if name == decorator or name.split(".")[-1] == decorator:
                    return True
            return False

        def _looks_state_modifying(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
            # Heuristics: keep intentionally conservative to avoid flooding.
            writeish = {
                "write",
                "write_text",
                "writelines",
                "unlink",
                "remove",
                "rmtree",
                "commit",
                "execute",
                "executemany",
                "add",
                "delete",
                "update",
                "insert",
                "save",
                "set",
                "put",
                "post",
            }
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        if (
                            isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == "self"
                        ):
                            return True
                if isinstance(n, ast.AugAssign):
                    if (
                        isinstance(n.target, ast.Attribute)
                        and isinstance(n.target.value, ast.Name)
                        and n.target.value.id == "self"
                    ):
                        return True
                if isinstance(n, ast.Call):
                    call_name = ASTHelpers.full_attr_name(n.func) or ""
                    leaf = call_name.split(".")[-1]
                    if leaf in writeish:
                        return True
            return False

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if ignore_tests and fn.name.startswith("test_"):
                continue
            if only_public and fn.name.startswith("_"):
                continue

            if _looks_state_modifying(fn) and not _has_decorator(fn):
                violations.append(
                    f"Function '{fn.name}' appears state-modifying but lacks required @{decorator} "
                    f"(line {ASTHelpers.lineno(fn)})."
                )

        return violations
