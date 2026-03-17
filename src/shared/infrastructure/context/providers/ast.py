# src/shared/infrastructure/context/providers/ast.py

"""ASTProvider - lightweight AST analysis for context evidence."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cd32d77e-e7e1-49a6-bafc-b69e9cd0218e
class ParentScopeFinder(ast.NodeVisitor):
    """Find the most specific parent scope for a given line number."""

    def __init__(self, line_number: int) -> None:
        self.line_number = line_number
        self.parent: ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef | None = None

    # ID: 2224b903-f772-48a3-ba93-28664614ec8e
    def visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)

            if start_line <= self.line_number <= end_line:
                self.parent = node

        self.generic_visit(node)


# ID: 2e3d7ffe-4588-4e75-9d49-1bbac6ce3fc6
class ASTProvider:
    """Provides AST-based analysis helpers for context evidence."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.root = Path(project_root).resolve()

    def _resolve_path(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        return path if path.is_absolute() else self.root / path

    # ID: fb68d89d-540d-4941-81c8-1c629291789d
    def read_source(self, file_path: str | Path) -> str | None:
        """Read source text from a file."""
        try:
            return self._resolve_path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Failed reading source for %s: %s", file_path, e)
            return None

    # ID: c9ff988f-180e-48db-87d3-2350c0fb9f32
    def get_ast_tree(self, file_path: str | Path) -> ast.Module | None:
        """Read and parse a file into an AST."""
        try:
            source = self.read_source(file_path)
            if source is None:
                return None
            return ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            logger.debug("Failed parsing AST for %s: %s", file_path, e)
            return None

    # ID: 8743a91b-456c-407e-b613-5bdb850c9e84
    def get_signature_from_tree(
        self,
        tree: ast.Module,
        symbol_name: str,
    ) -> str | None:
        """Extract a function/class signature from a parsed AST tree."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    node_copy = copy.copy(node)
                    node_copy.body = []
                    try:
                        return ast.unparse(node_copy)
                    except Exception as e:
                        logger.debug(
                            "Failed unparsing signature for %s: %s",
                            symbol_name,
                            e,
                        )
                        return None
        return None

    # ID: 9f12bc2e-119f-4aab-bd8a-1ba87a750e87
    def get_signature(self, file_path: str | Path, symbol_name: str) -> str | None:
        """Extract function/class signature from a file."""
        logger.debug("Extracting signature for %s in %s", symbol_name, file_path)
        tree = self.get_ast_tree(file_path)
        return self.get_signature_from_tree(tree, symbol_name) if tree else None

    # ID: afbb2bdb-049a-45ea-b889-55a9428144f1
    def get_dependencies_from_tree(self, tree: ast.Module) -> list[str]:
        """Extract import dependencies from a parsed AST tree."""
        deps: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    deps.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                deps.add(node.module)

        return sorted(deps)

    # ID: bccecfdc-1a5f-4246-83ee-687c0c86c2db
    def get_dependencies(self, file_path: str | Path) -> list[str]:
        """Extract import dependencies from a file."""
        logger.debug("Extracting dependencies from %s", file_path)
        tree = self.get_ast_tree(file_path)
        return self.get_dependencies_from_tree(tree) if tree else []

    # ID: 525a3cc7-724d-4c31-b9a1-92cbca3c8c8e
    def get_parent_scope_from_tree(
        self,
        tree: ast.Module,
        line_number: int,
    ) -> str | None:
        """Find the parent class/function at a given line in a parsed AST tree."""
        finder = ParentScopeFinder(line_number)
        finder.visit(tree)
        return finder.parent.name if finder.parent else None

    # ID: c0f6be43-24c5-4aa4-9d7d-49e311703507
    def get_parent_scope(self, file_path: str | Path, line_number: int) -> str | None:
        """Find parent class/function at a given line in a file."""
        logger.debug("Finding parent scope at %s:%s", file_path, line_number)
        tree = self.get_ast_tree(file_path)
        return self.get_parent_scope_from_tree(tree, line_number) if tree else None

    # ID: 1fb33ca3-f623-4601-922c-5882f8e3b48f
    def extract_symbols(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Extract top-level and nested class/function symbols from a file."""
        source = self.read_source(file_path)
        if source is None:
            return []

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            logger.debug(
                "Failed parsing AST for symbol extraction in %s: %s", file_path, e
            )
            return []

        lines = source.splitlines()
        symbols: list[dict[str, Any]] = []
        stack: list[str] = []

        # ID: 99b3f5ec-e209-47f3-874d-a6760b617bfb
        class Visitor(ast.NodeVisitor):
            # ID: 060d0386-a997-446b-b18f-43d1c0cc63c8
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                qualname = ".".join([*stack, node.name]) if stack else node.name
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                code = "\n".join(lines[node.lineno - 1 : end])
                symbols.append(
                    {
                        "name": node.name,
                        "qualname": qualname,
                        "signature": code.split("\n")[0],
                        "code": code,
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            # ID: adefde0b-4de5-4040-bc6a-757dfd4b96c0
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                qualname = ".".join([*stack, node.name]) if stack else node.name
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                code = "\n".join(lines[node.lineno - 1 : end])
                symbols.append(
                    {
                        "name": node.name,
                        "qualname": qualname,
                        "signature": code.split("\n")[0],
                        "code": code,
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
                self.generic_visit(node)

            # ID: e01bf02d-d6db-41af-a54f-36d529bc6961
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                qualname = ".".join([*stack, node.name]) if stack else node.name
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                code = "\n".join(lines[node.lineno - 1 : end])
                symbols.append(
                    {
                        "name": node.name,
                        "qualname": qualname,
                        "signature": code.split("\n")[0],
                        "code": code,
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
                self.generic_visit(node)

        Visitor().visit(tree)
        return symbols
