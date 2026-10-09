# src/shared/infrastructure/context/providers/ast.py

"""ASTProvider - lightweight AST analysis for context evidence."""

from __future__ import annotations

import ast
from pathlib import Path

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
