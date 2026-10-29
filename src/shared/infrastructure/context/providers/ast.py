# src/shared/infrastructure/context/providers/ast.py

"""ASTProvider - lightweight AST analysis for context evidence."""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2e3d7ffe-4588-4e75-9d49-1bbac6ce3fc6
class ASTProvider:
    """Provides AST-based analysis helpers for context evidence."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.root = Path(project_root).resolve()

    def _resolve_path(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        return path if path.is_absolute() else self.root / path
