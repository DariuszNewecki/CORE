# src/mind/logic/engines/ast_gate/checks/runtime_import_boundary.py
"""
Runtime Import Boundary Check — forbids cross-layer runtime imports.

Constitutional purpose:
Enforces layer-separation rules (mind/no_body_invocation,
will/no_database_access, shared/no_layer_imports, etc.) by detecting
forbidden imports at module top level and inside function bodies —
i.e. imports that actually run at process start or call time, creating
real layer coupling.

Type-level proprioception is allowed by default:
imports inside `if TYPE_CHECKING:` blocks are erased at runtime and do
not create execution coupling. The check skips them so that mind can
*know* a body type's name (for annotations) without *invoking* the body
module. Set ``params.type_checking_exempt: false`` to disable this
exemption for strict rules that must forbid even type-level references.

Renamed from ``import_boundary`` (issue #490, ADR-077). The previous
name described the mechanism (looks at imports); this one declares the
constitutional intent (forbids runtime invocation, allows proprioception).
The ``type_checking_exempt`` parameter is now visible in the rule YAML
rather than hidden in engine behaviour.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from mind.logic.engines.ast_gate.base import ASTHelpers
from mind.logic.engines.base import EngineResult


if TYPE_CHECKING:
    from pathlib import Path


# ID: 7f4a9b2c-8e1d-4f3a-9c2d-6b5e8a7f4c1d
class RuntimeImportBoundaryCheck:
    """
    Detects forbidden runtime cross-layer imports.

    Configuration (from YAML):
        check_type: runtime_import_boundary
        params:
          forbidden:
            - "src.body"
            - "body"
          type_checking_exempt: true   # default; set false for strict rules

    The ``type_checking_exempt`` flag controls whether imports inside
    ``if TYPE_CHECKING:`` blocks are skipped. Default true matches the
    Kubernetes/mypy/OPA convention: type hints don't create runtime
    coupling, so they don't violate runtime-invocation rules.

    Set to false only for rules whose constitutional intent is to forbid
    even compile-time references (e.g. "no part of mind shall name a
    secrets-handling type, even in annotations"). No current CORE rule
    needs this; the flag exists so the convention is configurable rather
    than hardcoded.
    """

    @staticmethod
    # ID: a3f7c9e1-4b2d-5e8f-a1c6-d9f4e7b2a8c3
    def check(
        filepath: Path,
        tree: ast.Module,
        params: dict,
    ) -> EngineResult:
        """Detect forbidden runtime imports based on constitutional boundaries."""
        forbidden_patterns = params.get("forbidden", [])
        if not forbidden_patterns:
            return EngineResult(
                ok=False,
                message="runtime_import_boundary check requires 'forbidden' parameter",
                violations=["Configuration error: no forbidden imports specified"],
                engine_id="ast_gate:runtime_import_boundary",
            )

        type_checking_exempt = params.get("type_checking_exempt", True)

        if type_checking_exempt:
            type_checking_nodes = RuntimeImportBoundaryCheck._find_type_checking_blocks(
                tree
            )
        else:
            type_checking_nodes = set()

        violations = []

        for node in ast.walk(tree):
            if node in type_checking_nodes:
                continue

            if isinstance(node, ast.ImportFrom):
                violation = RuntimeImportBoundaryCheck._check_import_from(
                    node, forbidden_patterns, filepath
                )
                if violation:
                    violations.append(violation)

            elif isinstance(node, ast.Import):
                violation = RuntimeImportBoundaryCheck._check_import(
                    node, forbidden_patterns, filepath
                )
                if violation:
                    violations.append(violation)

        if violations:
            return EngineResult(
                ok=False,
                message=f"Detected {len(violations)} forbidden runtime cross-layer imports",
                violations=violations,
                engine_id="ast_gate:runtime_import_boundary",
            )

        return EngineResult(
            ok=True,
            message="No forbidden runtime imports detected",
            violations=[],
            engine_id="ast_gate:runtime_import_boundary",
        )

    @staticmethod
    # ID: e5f9a2c7-d3b6-8e4f-c1a5-f7d2e9b4a6c8
    def _find_type_checking_blocks(tree: ast.Module) -> set[ast.AST]:
        """Return the set of AST nodes inside ``if TYPE_CHECKING:`` blocks."""
        type_checking_nodes: set[ast.AST] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.If) and ASTHelpers.is_type_checking_condition(
                node.test
            ):
                for stmt in node.body:
                    type_checking_nodes.add(stmt)
                    for nested in ast.walk(stmt):
                        type_checking_nodes.add(nested)

        return type_checking_nodes

    @staticmethod
    # ID: b8e2f6d3-9c4a-5f1e-a7b9-c3d8e1f5a2b6
    def _check_import_from(
        node: ast.ImportFrom,
        forbidden_patterns: list[str],
        filepath: Path,
    ) -> str | None:
        """Check ``from X import Y`` statements against the forbidden list."""
        if not node.module:
            return None

        lineno = ASTHelpers.lineno(node)

        for name in node.names:
            full_import = f"{node.module}.{name.name}"
            for pattern in forbidden_patterns:
                if RuntimeImportBoundaryCheck._matches_pattern(full_import, pattern):
                    return (
                        f"{filepath}:{lineno} - Forbidden import: "
                        f"'from {node.module} import {name.name}' "
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
        """Check ``import X`` statements against the forbidden list."""
        lineno = ASTHelpers.lineno(node)

        for alias in node.names:
            for pattern in forbidden_patterns:
                if RuntimeImportBoundaryCheck._matches_pattern(alias.name, pattern):
                    return (
                        f"{filepath}:{lineno} - Forbidden import: "
                        f"'import {alias.name}' "
                        f"(matches constitutional boundary rule: {pattern})"
                    )

        return None

    @staticmethod
    # ID: d2f8e4c1-b5a7-9e3f-c6d2-a9f7e4b1c8d5
    def _matches_pattern(import_path: str, pattern: str) -> bool:
        """Exact, prefix, or subpath match against the forbidden pattern."""
        if import_path == pattern:
            return True
        if import_path.startswith(pattern + "."):
            return True
        if pattern.startswith(import_path + "."):
            return True
        return False
