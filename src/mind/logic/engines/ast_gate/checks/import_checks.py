# src/mind/logic/engines/ast_gate/checks/import_checks.py
"""Import-related AST checks for constitutional enforcement."""

from __future__ import annotations

import ast
import sys

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: dc735295-6a26-4908-a08f-a8c74c27d83a
class ImportChecks:
    """Import boundary and linting checks."""

    @staticmethod
    # ID: 86bdd1f7-c822-445c-9d91-dc40acb224b9
    def check_forbidden_imports(tree: ast.AST, forbidden: list[str]) -> list[str]:
        """
        Enforce import_boundary rule.

        BIG BOYS PATTERN:
        Allows TYPE_CHECKING imports (runtime-erased, tooling only).
        Only blocks actual runtime imports that create coupling.
        """
        if not forbidden:
            return []

        findings: list[str] = []
        forbidden_set = set(forbidden)

        # First pass: find all TYPE_CHECKING blocks
        type_checking_nodes = ImportChecks._find_type_checking_blocks(tree)

        for node in ast.walk(tree):
            # Skip imports inside TYPE_CHECKING blocks
            if node in type_checking_nodes:
                continue

            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imported = alias.name
                    fq = f"{mod}.{imported}" if mod else imported
                    if fq in forbidden_set:
                        findings.append(
                            f"Line {ASTHelpers.lineno(node)}: Forbidden import-from '{fq}'"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    if mod in forbidden_set:
                        findings.append(
                            f"Line {ASTHelpers.lineno(node)}: Forbidden import '{mod}'"
                        )

        return findings

    @staticmethod
    def _find_type_checking_blocks(
        tree: ast.Module,
    ) -> set[ast.stmt]:  # ← Changed from set[ast.AST]
        """Find all nodes inside TYPE_CHECKING blocks."""
        type_checking_nodes: set[ast.stmt] = set()  # ← Added explicit type annotation

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if ASTHelpers.is_type_checking_condition(node.test):
                    for stmt in node.body:
                        type_checking_nodes.add(stmt)
                        for nested in ast.walk(stmt):
                            if isinstance(nested, ast.stmt):  # ← Type guard
                                type_checking_nodes.add(nested)

        return type_checking_nodes

    @staticmethod
    # ID: 99a2ce26-dc0d-4bf9-ae39-2eb8082fb4fa
    def check_import_order(
        tree: ast.AST, params: dict, source: str | None = None
    ) -> list[str]:
        """Enforce import ordering: future → stdlib → third-party → internal."""
        if not isinstance(tree, ast.Module):
            return []

        stdlib_names = set(params.get("stdlib_modules", [])) or sys.stdlib_module_names
        internal_roots = set(
            params.get("internal_roots", ["shared", "mind", "body", "will", "features"])
        )

        import_block: list[ast.stmt] = []
        for stmt in tree.body:
            if (
                not import_block
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue

            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                import_block.append(stmt)
                continue

            break

        if not import_block:
            return []

        def _root_of_import(stmt: ast.stmt) -> list[str]:
            roots: list[str] = []
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    roots.append(alias.name.split(".")[0])
                return roots
            if isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                roots.append(mod.split(".")[0] if mod else "")
                return roots
            return roots

        def _classify_root(root: str, stmt: ast.stmt) -> str:
            if isinstance(stmt, ast.ImportFrom) and (stmt.module or "") == "__future__":
                return "future"
            if root in stdlib_names:
                return "stdlib"
            if root in internal_roots:
                return "internal"
            return "third_party"

        order_index = {"future": 0, "stdlib": 1, "third_party": 2, "internal": 3}

        findings: list[str] = []
        seen_max = -1

        for stmt in import_block:
            roots = [r for r in _root_of_import(stmt) if r]
            groups = {_classify_root(r, stmt) for r in roots} if roots else set()

            if len(groups) > 1:
                findings.append(
                    f"Line {ASTHelpers.lineno(stmt)}: Mixed import groups in single statement"
                )
                grp = "third_party"
            else:
                grp = next(iter(groups), "third_party")

            idx = order_index.get(grp, 99)
            if idx < seen_max:
                findings.append(
                    f"Line {ASTHelpers.lineno(stmt)}: Imports not properly grouped"
                )
            seen_max = max(seen_max, idx)

        return findings
