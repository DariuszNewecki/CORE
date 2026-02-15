# src/mind/logic/engines/ast_gate/checks/capability_checks.py
"""
Capability linkage checks for constitutional enforcement.

Verifies that code symbols are properly linked to capabilities in the
knowledge graph for governance tracking and autonomous operations.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.base import ASTHelpers
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: de2667dc-239d-408a-b9b0-fa59ea3a6a66
class CapabilityChecks:
    """Capability linkage and governance checks."""

    def __init__(self, path_resolver: PathResolver):
        self._paths = path_resolver

    # ID: 2c6bf9cf-2b1b-4e45-a195-a15073f65e3e
    def check_capability_assignment(
        self,
        tree: ast.AST,
        *,
        file_path: Path,
        source: str | None = None,
    ) -> list[str]:
        """
        Enforce linkage.capability.unassigned: Public symbols must have
        capability IDs assigned in the knowledge graph.

        This check:
        1. Finds all public symbols in the file (functions/classes)
        2. Queries knowledge graph for their capability assignments
        3. Reports symbols with capability='unassigned'

        Exclusions (per policy):
        - Private symbols (name starts with _)
        - Test files (tests/**/*.py)
        - Magic methods (__init__, __str__, etc.)

        Args:
            tree: AST of the file
            file_path: Absolute path to the file
            source: Source code (optional, not used currently)

        Returns:
            List of violation messages
        """
        findings: list[str] = []

        # Get relative path for exclusion checks
        try:
            rel_path = str(file_path.relative_to(self._paths.repo_root))
        except ValueError:
            rel_path = str(file_path)

        # Exclusion: Intent files
        try:
            file_path.relative_to(self._paths.intent_root)
            return findings
        except ValueError:
            pass

        # Exclusion: Test files
        if "tests/" in rel_path or rel_path.startswith("tests/"):
            return findings

        # Exclusion: Scripts
        if "scripts/" in rel_path or rel_path.startswith("scripts/"):
            return findings

        # Collect public symbols from AST
        public_symbols = _extract_public_symbols(tree)

        if not public_symbols:
            return findings

        # Query knowledge graph for capability assignments
        try:
            kg_service = KnowledgeService(self._paths.repo_root)
            graph = kg_service.get_graph_sync()  # Synchronous version for AST check
            symbols_data = graph.get("symbols", {})

            # Check each public symbol
            for symbol_name, lineno in public_symbols:
                # Find symbol in knowledge graph
                symbol_info = _find_symbol_in_kg(symbols_data, symbol_name, rel_path)

                if symbol_info is None:
                    # Symbol not in KG at all - different violation
                    # (handled by other checks)
                    continue

                capability = symbol_info.get("capability")

                if capability == "unassigned":
                    findings.append(
                        f"Line {lineno}: Public symbol '{symbol_name}' has "
                        f"capability='unassigned' in knowledge graph. "
                        f"Run 'core-admin dev sync --write' to assign capability."
                    )

        except Exception as e:
            logger.warning(
                "Could not check capability assignments for %s: %s",
                file_path,
                e,
            )
            # Don't fail the check - knowledge graph might not be built yet
            # This is informational, not blocking

        return findings


# ID: c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f
def _extract_public_symbols(tree: ast.AST) -> list[tuple[str, int]]:
    """
    Extract public symbols (functions/classes) from AST.

    Returns:
        List of (symbol_name, line_number) tuples
    """
    symbols: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name

            # Exclusion: Private symbols
            if name.startswith("_"):
                continue

            # Exclusion: Magic methods (already private, but double-check)
            if name.startswith("__") and name.endswith("__"):
                continue

            lineno = ASTHelpers.lineno(node)
            symbols.append((name, lineno))

    return symbols


# ID: d4e5f6a7-8b9c-0d1e-2f3a-4b5c6d7e8f9a
def _find_symbol_in_kg(
    symbols_data: dict,
    symbol_name: str,
    file_path: str,
) -> dict | None:
    """
    Find symbol in knowledge graph by name and file path.

    Knowledge graph keys are like: "src/path/file.py::ClassName.method_name"

    Args:
        symbols_data: Knowledge graph symbols dict
        symbol_name: Name of symbol to find
        file_path: Relative file path

    Returns:
        Symbol data dict or None if not found
    """
    # Try exact match first (most common case)
    for key, data in symbols_data.items():
        if not isinstance(data, dict):
            continue

        # Check if this symbol matches
        kg_name = data.get("name")
        kg_file = data.get("file_path", "")

        if kg_name == symbol_name and file_path in kg_file:
            return data

    # Try fuzzy match (symbol might be part of qualified name)
    for key, data in symbols_data.items():
        if not isinstance(data, dict):
            continue

        kg_name = data.get("name", "")
        kg_file = data.get("file_path", "")

        # Check if symbol name appears in qualified name
        if symbol_name in kg_name and file_path in kg_file:
            return data

    return None
