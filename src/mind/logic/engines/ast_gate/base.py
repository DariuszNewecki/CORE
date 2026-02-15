# src/mind/logic/engines/ast_gate/base.py
# ID: 08acf631-aeea-4ad9-9107-c6100b89942f

"""
Shared AST analysis utilities for constitutional enforcement.

Provides common helpers for traversing and analyzing Python AST nodes.
CONSTITUTIONAL FIX (V2.3.9):
- Added 'extract_domain_from_path' to centralize architectural layout knowledge.
- Added 'domain_matches' to support trust-zone based enforcement.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path


# ID: f75299d7-84aa-4254-8a2d-0e17da174d45
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
        - Exact match on fully qualified name (e.g., "asyncio.run" == "asyncio.run")
        - Suffix match with dot (e.g., "foo.asyncio.run" matches "asyncio.run")

        DOES NOT match bare leaf names to prevent false positives.
        Example: "subprocess.run" will NOT match "asyncio.run"

        Args:
            call_name: Fully qualified call name from AST (e.g., "asyncio.run")
            disallowed: List of forbidden call patterns (e.g., ["asyncio.run"])

        Returns:
            True if call_name matches any disallowed pattern
        """
        for pattern in disallowed:
            # Strategy 1: Exact match
            if call_name == pattern:
                return True

            # Strategy 2: Suffix match (handles nested imports)
            if "." in pattern:
                # Only match if it's a proper suffix with a dot boundary
                if call_name.endswith(f".{pattern}") or call_name.endswith(pattern):
                    call_parts = call_name.split(".")
                    pattern_parts = pattern.split(".")

                    if len(call_parts) >= len(pattern_parts):
                        # Check if the rightmost N parts match
                        if call_parts[-len(pattern_parts) :] == pattern_parts:
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

    # -------------------------------------------------------------------------
    # NEW ARCHITECTURAL HELPERS (Constitutional Mapping Logic)
    # -------------------------------------------------------------------------

    @staticmethod
    # ID: e4d3c2b1-a0f9-8e7d-6c5b-4a3f2e1d0c9b
    def extract_domain_from_path(file_path: Path | str) -> str:
        """
        Extract domain from file path following CORE's domain convention.

        Example: 'src/mind/governance/auditor.py' -> 'mind.governance'
        """
        path_str = str(file_path).replace("\\", "/")

        if "/src/" in path_str:
            path_str = path_str.split("/src/", 1)[1]
        elif path_str.startswith("src/"):
            path_str = path_str[4:]

        parts = path_str.split("/")
        domain_parts = [p for p in parts[:-1] if p]

        return ".".join(domain_parts) if domain_parts else ""

    @staticmethod
    # ID: f3e2d1c0-b9a8-7f6e-5d4c-3b2a1f0e9d8c
    def domain_matches(file_domain: str, allowed_domains: list[str]) -> bool:
        """
        Check if file domain matches any allowed domain (exact or prefix).
        """
        if not file_domain or not allowed_domains:
            return False

        for allowed in allowed_domains:
            if file_domain == allowed or file_domain.startswith(f"{allowed}."):
                return True

        return False

    @staticmethod
    # ID: 337aed3b-dc01-4b17-bbe3-e8498e1dee13
    def is_type_checking_condition(test_node: ast.expr) -> bool:
        """
        Check if an If condition is checking TYPE_CHECKING.

        Matches:
        - TYPE_CHECKING
        - typing.TYPE_CHECKING

        Args:
            test_node: The test expression from an ast.If node

        Returns:
            True if the condition checks TYPE_CHECKING

        Examples:
            >>> # Matches: if TYPE_CHECKING:
            >>> # Matches: if typing.TYPE_CHECKING:
        """
        if isinstance(test_node, ast.Name):
            return test_node.id == "TYPE_CHECKING"

        if isinstance(test_node, ast.Attribute):
            # Handle typing.TYPE_CHECKING
            if test_node.attr == "TYPE_CHECKING":
                if isinstance(test_node.value, ast.Name):
                    return test_node.value.id == "typing"

        return False
