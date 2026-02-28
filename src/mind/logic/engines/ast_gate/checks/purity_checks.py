# src/mind/logic/engines/ast_gate/checks/purity_checks.py
# ID: 6b2a85b5-2b76-4db7-bfb4-4f3a8b7b5f11

"""
Purity Checks - Deterministic AST-based enforcement.

CONSTITUTIONAL FIX (V2.3.0):
- Modularized to reduce Modularity Debt (49.9 -> ~36.0).
- Delegated Path/Domain resolution to 'ASTHelpers'.
- Compressed 'Intelligence Layer' heuristics into data-driven patterns.
- Preserves all 7 distinct constitutional check types.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from ..base import ASTHelpers


# ID: 318924b3-cfe8-4ae2-a856-88deacf02a9b
class PurityChecks:
    """
    Stateless collection of purity and standard enforcement checks.

    Refactored to be a 'Thin Neuron' that delegates structural facts to ASTHelpers.
    """

    _ID_ANCHOR_PREFIXES: ClassVar[tuple[str, ...]] = ("# ID:",)

    @staticmethod
    # ID: d0d9b1d6-5849-486a-9f77-8333f4fd75a4
    def check_stable_id_anchor(source: str) -> list[str]:
        """Ensures all PUBLIC symbols have an '# ID:' anchor above them."""
        violations = []
        try:
            tree = ast.parse(source)
            lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name.startswith("_"):
                        continue

                    # Identifies line immediately above definition
                    idx = node.lineno - 2
                    if idx < 0 or not lines[idx].strip().startswith(
                        PurityChecks._ID_ANCHOR_PREFIXES
                    ):
                        violations.append(
                            f"Public symbol '{node.name}' missing stable ID anchor (line {node.lineno})."
                        )
        except Exception:
            pass
        return violations

    @staticmethod
    # ID: 1cc2a7f3-5e21-4c10-9f93-5d2b7bdb3a65
    def check_forbidden_decorators(tree: ast.AST, forbidden: list[str]) -> list[str]:
        """Prevents use of obsolete metadata decorators in source code."""
        violations, forbidden_set = [], {d.strip() for d in forbidden if d.strip()}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    name = ASTHelpers.full_attr_name(dec)
                    if name in forbidden_set:
                        violations.append(
                            f"Forbidden decorator '{name}' on '{node.name}' (line {ASTHelpers.lineno(dec)})."
                        )
        return violations

    @staticmethod
    # ID: 8d7c6b5a-4e3f-2d1c-0b9a-8f7e6d5c4b3a
    def check_forbidden_primitives(
        tree: ast.AST,
        forbidden: list[str],
        file_path: Path | None = None,
        allowed_domains: list[str] | None = None,
    ) -> list[str]:
        """Check for dangerous primitives (eval/exec) with trust-zone awareness."""
        violations, forbidden_set = [], {p.strip() for p in forbidden if p.strip()}

        if file_path and allowed_domains:
            domain = ASTHelpers.extract_domain_from_path(file_path)
            if ASTHelpers.domain_matches(domain, allowed_domains):
                return []

        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name) and node.id in forbidden_set:
                name = node.id
            elif (
                isinstance(node, ast.Attribute)
                and (attr := ASTHelpers.full_attr_name(node)) in forbidden_set
            ):
                name = attr

            if name:
                violations.append(
                    f"Forbidden primitive '{name}' used (line {ASTHelpers.lineno(node)})."
                )
        return violations

    @staticmethod
    # ID: 5425f58f-517d-4f2e-b0db-1c4638565b73
    def check_no_print_statements(tree: ast.AST) -> list[str]:
        """Enforces standard logging over print()."""
        return [
            f"Line {ASTHelpers.lineno(n)}: Replace print() with logger."
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and ASTHelpers.full_attr_name(n.func) == "print"
        ]

    @staticmethod
    # ID: a4b3c2d1-e0f9-8e7d-6c5b-4a3f2e1d0c9b
    def check_required_decorator(
        tree: ast.AST, decorator: str, file_path: Path | None = None, **kwargs
    ) -> list[str]:
        """Ensures state-modifying functions use governance decorators (e.g., @atomic_action)."""
        # SANCTUARY ZONE: Core infrastructure and low-level processors are exempt
        if file_path:
            p_str = str(file_path).replace("\\", "/")
            if any(
                x in p_str
                for x in [
                    "shared/infrastructure",
                    "shared/processors",
                    "repositories/db",
                ]
            ):
                return []

        violations = []
        # Heuristic: Functions with these tools/methods are considered 'Armed and Acting'
        mutating_tools = {"session", "db", "file_handler", "fs", "repo_path"}
        mutating_methods = {
            "write",
            "delete",
            "create",
            "save",
            "persist",
            "apply",
            "commit",
            "add",
            "update",
        }

        for fn in ast.walk(tree):
            if not isinstance(
                fn, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) or fn.name.startswith(("_", "test_")):
                continue

            # 1. Tool Check (Arguments)
            args = {a.arg.lower() for a in [*fn.args.args, *fn.args.kwonlyargs]}
            if not any(t in args for t in mutating_tools):
                continue

            # 2. Action Check (Calls)
            is_acting = any(
                isinstance(c, ast.Call)
                and isinstance(c.func, ast.Attribute)
                and c.func.attr in mutating_methods
                for c in ast.walk(fn)
            )

            # 3. Decision: Flag if acting without the required decorator
            if is_acting and not any(
                ASTHelpers.full_attr_name(d) == decorator for d in fn.decorator_list
            ):
                violations.append(
                    f"Function '{fn.name}' appears state-modifying but lacks @{decorator} (line {fn.lineno})."
                )

        return violations

    @staticmethod
    # ID: 2dd7a4b8-fc4e-468e-9a1a-315acb2b3d6f
    def check_decorator_args(
        tree: ast.AST, decorator: str, required_args: list[str]
    ) -> list[str]:
        """Validates that specific decorators are called with mandatory keyword arguments."""
        violations, required_set = [], {a.strip() for a in required_args if a.strip()}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        if (
                            name := ASTHelpers.full_attr_name(dec.func)
                        ) == decorator or (name and name.split(".")[-1] == decorator):
                            present = {kw.arg for kw in dec.keywords if kw.arg}
                            missing = sorted(list(required_set - present))
                            if missing:
                                violations.append(
                                    f"@{decorator} on '{node.name}' missing required args {missing} (line {node.lineno})."
                                )
        return violations

    @staticmethod
    # ID: b7d320ba-ce8b-4274-8576-a254eeb58bd0
    def check_no_direct_writes(tree: ast.AST) -> list[str]:
        """Enforces the 'Governed Mutation Surface' by blocking raw filesystem writes."""
        violations = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                name = ASTHelpers.full_attr_name(n.func)
                # Matches Path.write_text(), Path.write_bytes(), and open() in write/append modes
                if name in ("write_text", "write_bytes") or (
                    name == "open" and _is_write_mode(n)
                ):
                    violations.append(
                        f"Direct write detected: '{name}' (line {ASTHelpers.lineno(n)}). Use FileHandler."
                    )
        return violations


def _is_write_mode(node: ast.Call) -> bool:
    """Internal helper to detect 'w' or 'a' in file open() calls."""
    # Check positional arguments and keyword 'mode' argument
    for arg in node.args + [k.value for k in node.keywords if k.arg == "mode"]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if any(m in arg.value for m in "wa"):
                return True
    return False
