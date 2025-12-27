# src/mind/logic/engines/ast_gate/base.py
"""
Shared AST analysis utilities for constitutional enforcement.

Provides common helpers for traversing and analyzing Python AST nodes.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable


# ID: 08acf631-aeea-4ad9-9107-c6100b89942f
class ASTHelpers:
    """
    Reusable AST traversal and analysis utilities.

    Used by all AST check implementations to avoid duplication.
    """

    @staticmethod
    # ID: b338ca12-adb5-482c-8399-a691192ee7ae
    def lineno(node: ast.AST) -> int:
        """Extract line number from AST node."""
        return int(getattr(node, "lineno", 0) or 0)

    @staticmethod
    # ID: 533311f7-6f83-4660-a3b7-1db18d2a60ce
    def full_attr_name(node: ast.AST) -> str | None:
        """
        Resolve dotted name from ast.Name / ast.Attribute chains.

        Examples:
            asyncio.run  -> "asyncio.run"
            loop.create_task -> "loop.create_task"
            create_async_engine -> "create_async_engine"
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = ASTHelpers.full_attr_name(node.value)
            if left:
                return f"{left}.{node.attr}"
            return node.attr
        return None

    @staticmethod
    # ID: e5fec108-e53c-4611-9ccb-1b17f9d3523b
    def matches_call(call_name: str, disallowed: list[str]) -> bool:
        """
        Match call name against disallowed patterns.

        Strategies:
        - Exact match on fully qualified name
        - Exact match on leaf name (last segment)
        - Suffix match (e.g., endswith ".create_async_engine")
        """
        leaf = call_name.split(".")[-1]
        for item in disallowed:
            if call_name == item:
                return True
            if leaf == item:
                return True
            if item.startswith(".") and call_name.endswith(item):
                return True
            if item.endswith(f".{leaf}") and call_name.endswith(f".{leaf}"):
                return True
        return False

    @staticmethod
    # ID: 9e091307-b265-4f46-8a62-e6b4ac1681eb
    def iter_module_level_stmts(tree: ast.AST) -> Iterable[ast.stmt]:
        """Iterate over module-level statements."""
        if isinstance(tree, ast.Module):
            return tree.body
        return []

    @staticmethod
    # ID: 10e7f915-2059-4010-afe6-6be56b2084fb
    def walk_module_stmt_without_nested_scopes(stmt: ast.stmt) -> Iterable[ast.AST]:
        """
        Walk statement but don't descend into nested scopes.

        Skips: function defs, class defs, lambdas
        """

        def _walk(node: ast.AST) -> Iterable[ast.AST]:
            yield node
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
                ):
                    continue
                yield from _walk(child)

        return _walk(stmt)
