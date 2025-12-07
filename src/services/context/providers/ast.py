# src/services/context/providers/ast.py

"""ASTProvider - Lightweight AST analysis for context enrichment."""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

import ast
import copy
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


# ID: 166b4121-3aad-464b-89fe-786d4b8c930d
class ParentScopeFinder(ast.NodeVisitor):
    """An AST visitor that finds the most specific parent scope for a given line number."""

    def __init__(self, line_number: int):
        self.line_number = line_number
        self.parent: ast.FunctionDef | ast.ClassDef | None = None

    # ID: b172d7e0-1f24-420f-b1d0-32af75acd8fa
    def visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)

            if start_line <= self.line_number <= end_line:
                self.parent = node

        self.generic_visit(node)


# ID: 5c65c20d-5f9e-4f8e-89d2-1968769b3cbc
class ASTProvider:
    """Provides AST-based analysis for context enrichment."""

    def __init__(self, project_root: str | Path = "."):
        self.root = Path(project_root).resolve()

    def _get_ast_tree(self, file_path: Path) -> ast.Module | None:
        """Reads a file and returns its parsed AST tree."""
        try:
            full_path = (
                self.root / file_path if not file_path.is_absolute() else file_path
            )
            source = full_path.read_text(encoding="utf-8")
            return ast.parse(source, filename=str(file_path))
        except (OSError, SyntaxError, UnicodeDecodeError) as e:
            logger.error("Failed to read or parse AST for {file_path}: %s", e)
            return None

    # ID: e81360dc-3fa1-4196-9e21-cd6cf9636455
    def get_signature_from_tree(self, tree: ast.Module, symbol_name: str) -> str | None:
        """Extracts a function/class signature from a parsed AST tree."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    # CORRECTED LOGIC: Use copy.copy and then modify the body.
                    node_copy = copy.copy(node)
                    node_copy.body = []  # Remove the function/class body

                    return ast.unparse(node_copy)
        return None

    # ID: 3825937d-cf44-48bd-b344-3cb2c03dad2f
    def get_signature(self, file_path: str | Path, symbol_name: str) -> str | None:
        """Extract function/class signature from a file."""
        logger.debug("Extracting signature for {symbol_name} in %s", file_path)
        tree = self._get_ast_tree(Path(file_path))
        return self.get_signature_from_tree(tree, symbol_name) if tree else None

    # ID: 25ca7f92-c112-4a93-83a5-bd8cacaca516
    def get_dependencies_from_tree(self, tree: ast.Module) -> list[str]:
        """Extracts import dependencies from a parsed AST tree."""
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    deps.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.add(node.module)
        return sorted(list(deps))

    # ID: 5f4ad62e-e2d9-405e-bb00-ae24b5e5e32e
    def get_dependencies(self, file_path: str | Path) -> list[str]:
        """Extract import dependencies from a file."""
        logger.debug("Extracting dependencies from %s", file_path)
        tree = self._get_ast_tree(Path(file_path))
        return self.get_dependencies_from_tree(tree) if tree else []

    # ID: 525ae58c-7928-438c-a9f7-fe0daf4f4a95
    def get_parent_scope_from_tree(
        self, tree: ast.Module, line_number: int
    ) -> str | None:
        """Finds the parent class/function at a given line in a parsed AST tree."""
        finder = ParentScopeFinder(line_number)
        finder.visit(tree)
        return finder.parent.name if finder.parent else None

    # ID: ae4e8872-feb6-4ff5-bdad-3b4864a58a07
    def get_parent_scope(self, file_path: str | Path, line_number: int) -> str | None:
        """Find parent class/function at a given line in a file."""
        logger.debug("Finding parent scope at {file_path}:%s", line_number)
        tree = self._get_ast_tree(Path(file_path))
        return self.get_parent_scope_from_tree(tree, line_number) if tree else None
