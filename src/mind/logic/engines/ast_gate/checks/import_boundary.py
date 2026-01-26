# src/mind/logic/engines/ast_gate/checks/import_boundary.py
"""
Import Boundary Check - Enforces privileged primitive access restrictions.

Constitutional Purpose:
Prevents architectural drift by blocking direct imports of infrastructure
primitives in layers that should use dependency injection.

Examples:
- Mind layer importing get_session (law executing itself)
- Will layer importing FileHandler (decision implementing itself)
- Body layer importing IntentLoader (execution reading law directly)

This check enforces Mind/Body/Will separation at import time.

BIG BOYS PATTERN:
Allows TYPE_CHECKING imports for type hints (runtime-erased, tooling only).
Only blocks actual runtime imports that create coupling.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from mind.logic.engines.ast_gate.base import ASTHelpers
from mind.logic.engines.base import EngineResult


if TYPE_CHECKING:
    from pathlib import Path


# ID: 7f4a9b2c-8e1d-4f3a-9c2d-6b5e8a7f4c1d
class ImportBoundaryCheck:
    """
    Detects forbidden imports of infrastructure primitives.

    Enforces constitutional rule: certain components may not directly
    import infrastructure primitives and must use dependency injection.

    Configuration (from YAML):
        forbidden:
          - "shared.infrastructure.database.session_manager.get_session"
          - "core.infrastructure.config.Settings"
          - "mind.intent.loader.IntentLoader"

    Rationale:
    - Mind layer must not access database (law executing itself)
    - Will layer must not access database directly (decision implementing itself)
    - Non-Mind layers must not access IntentLoader (bypassing constitutional interface)

    TYPE_CHECKING Exception:
    - Imports inside `if TYPE_CHECKING:` blocks are allowed (type hints only)
    - These are erased at runtime and don't create actual coupling
    - Following Kubernetes/mypy/OPA pattern
    """

    @staticmethod
    # ID: a3f7c9e1-4b2d-5e8f-a1c6-d9f4e7b2a8c3
    def check(
        filepath: Path,
        tree: ast.Module,
        params: dict,
    ) -> EngineResult:
        """
        Detect forbidden imports based on constitutional boundaries.

        Args:
            filepath: File being checked
            tree: Parsed AST
            params: Must contain 'forbidden' list of import patterns

        Returns:
            EngineResult with violations if forbidden imports detected
        """
        forbidden_patterns = params.get("forbidden", [])
        if not forbidden_patterns:
            return EngineResult(
                ok=False,
                message="import_boundary check requires 'forbidden' parameter",
                violations=["Configuration error: no forbidden imports specified"],
                engine_id="ast_gate:import_boundary",
            )

        # First pass: identify all TYPE_CHECKING blocks
        type_checking_nodes = ImportBoundaryCheck._find_type_checking_blocks(tree)

        violations = []

        for node in ast.walk(tree):
            # Skip imports inside TYPE_CHECKING blocks
            if ImportBoundaryCheck._is_inside_type_checking(node, type_checking_nodes):
                continue

            # Check: from X import Y
            if isinstance(node, ast.ImportFrom):
                violation = ImportBoundaryCheck._check_import_from(
                    node, forbidden_patterns, filepath
                )
                if violation:
                    violations.append(violation)

            # Check: import X
            elif isinstance(node, ast.Import):
                violation = ImportBoundaryCheck._check_import(
                    node, forbidden_patterns, filepath
                )
                if violation:
                    violations.append(violation)

        if violations:
            return EngineResult(
                ok=False,
                message=f"Detected {len(violations)} forbidden infrastructure primitive imports",
                violations=violations,
                engine_id="ast_gate:import_boundary",
            )

        return EngineResult(
            ok=True,
            message="No forbidden imports detected",
            violations=[],
            engine_id="ast_gate:import_boundary",
        )

    @staticmethod
    # ID: e5f9a2c7-d3b6-8e4f-c1a5-f7d2e9b4a6c8
    def _find_type_checking_blocks(tree: ast.Module) -> set[ast.AST]:
        """
        Find all nodes inside TYPE_CHECKING conditional blocks.

        Detects pattern:
            if TYPE_CHECKING:
                from x import Y

        Returns set of all AST nodes within these blocks.
        """
        type_checking_nodes = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check if condition is TYPE_CHECKING
                if ImportBoundaryCheck._is_type_checking_condition(node.test):
                    # Add all nodes in the if body
                    for stmt in node.body:
                        type_checking_nodes.add(stmt)
                        # Also add all nested nodes
                        for nested in ast.walk(stmt):
                            type_checking_nodes.add(nested)

        return type_checking_nodes

    @staticmethod
    # ID: f6a8b3d9-e4c7-9f5a-d2b6-a8e3f7c5d4b1
    def _is_type_checking_condition(test_node: ast.expr) -> bool:
        """
        Check if an If condition is checking TYPE_CHECKING.

        Matches:
        - TYPE_CHECKING
        - typing.TYPE_CHECKING
        """
        if isinstance(test_node, ast.Name):
            return test_node.id == "TYPE_CHECKING"

        if isinstance(test_node, ast.Attribute):
            # Handle typing.TYPE_CHECKING
            if test_node.attr == "TYPE_CHECKING":
                if isinstance(test_node.value, ast.Name):
                    return test_node.value.id == "typing"

        return False

    @staticmethod
    # ID: a7d9c4e2-f5b8-a6e9-c3d7-b9f4e8a2c5d6
    def _is_inside_type_checking(
        node: ast.AST, type_checking_nodes: set[ast.AST]
    ) -> bool:
        """Check if node is inside a TYPE_CHECKING block."""
        return node in type_checking_nodes

    @staticmethod
    # ID: b8e2f6d3-9c4a-5f1e-a7b9-c3d8e1f5a2b6
    def _check_import_from(
        node: ast.ImportFrom,
        forbidden_patterns: list[str],
        filepath: Path,
    ) -> str | None:
        """
        Check 'from X import Y' statement for forbidden imports.

        Matches patterns like:
        - "shared.infrastructure.database.session_manager.get_session"
        - "core.infrastructure.config.Settings"

        Returns violation string if forbidden, None otherwise.
        """
        if not node.module:
            return None

        lineno = ASTHelpers.lineno(node)

        for name in node.names:
            imported_name = name.name
            full_import = f"{node.module}.{imported_name}"

            # Check if this import matches any forbidden pattern
            for pattern in forbidden_patterns:
                if ImportBoundaryCheck._matches_pattern(full_import, pattern):
                    return (
                        f"{filepath}:{lineno} - Forbidden import: "
                        f"'from {node.module} import {imported_name}' "
                        f"(matches constitutional boundary rule: {pattern})"
                    )

        return None

    @staticmethod
    # ID: c9d4e7f2-a3b5-6e8c-b4d1-f8a7c2e5b3d9
    def _check_import(
        node: ast.Import,
        forbidden_patterns: list[str],
        filepath: Path,
    ) -> str | None:
        """
        Check 'import X' statement for forbidden imports.

        Matches patterns like:
        - "shared.infrastructure.database"
        - "core.infrastructure.config"

        Returns violation string if forbidden, None otherwise.
        """
        lineno = ASTHelpers.lineno(node)

        for alias in node.names:
            imported_module = alias.name

            # Check if this import matches any forbidden pattern
            for pattern in forbidden_patterns:
                # For 'import X' we check if X is part of forbidden pattern
                if ImportBoundaryCheck._matches_pattern(imported_module, pattern):
                    return (
                        f"{filepath}:{lineno} - Forbidden import: "
                        f"'import {imported_module}' "
                        f"(matches constitutional boundary rule: {pattern})"
                    )

        return None

    @staticmethod
    # ID: d2f8e4c1-b5a7-9e3f-c6d2-a9f7e4b1c8d5
    def _matches_pattern(import_path: str, pattern: str) -> bool:
        """
        Check if import path matches forbidden pattern.

        Supports exact match and prefix match:
        - "shared.config.Settings" matches "shared.config.Settings" (exact)
        - "shared.config" matches "shared.config.*" (prefix)
        - "shared.config.settings" matches "shared.config" (contains)

        Args:
            import_path: The actual import statement (e.g., "shared.config.Settings")
            pattern: The forbidden pattern from rule (e.g., "shared.config.Settings")

        Returns:
            True if import violates boundary
        """
        # Exact match
        if import_path == pattern:
            return True

        # Check if import starts with pattern (e.g., importing module that contains forbidden)
        if import_path.startswith(pattern + "."):
            return True

        # Check if pattern is a subpath of import (e.g., pattern is more specific)
        if pattern.startswith(import_path + "."):
            return True

        return False
