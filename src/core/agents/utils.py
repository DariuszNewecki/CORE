# src/agents/utils.py
"""
Utility classes and functions for CORE agents including symbol location
and plan execution context management.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from core.git_service import GitService
from shared.logger import getLogger
from shared.models import PlannerConfig

log = getLogger(__name__)


# ID: fd0b06b9-209b-4cdf-bac1-79b179e5810a
class SymbolLocator:
    """Dedicated class for finding symbols in code files."""

    @staticmethod
    # ID: 2d44d022-7e57-4ab6-8bef-bcf0ae9ed360
    def find_symbol_line(file_path: Path, symbol_name: str) -> Optional[int]:
        """Find the 1-based line number of a function or class definition in a file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name == symbol_name:
                        return node.lineno
        except (SyntaxError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Failed to parse {file_path}: {e}") from e
        return None


# ID: 6eba16a2-dd3b-4f89-b993-9ebc9eca5f1e
class PlanExecutionContext:
    """Context manager for safe plan execution with rollback."""

    def __init__(self, git_service: GitService, config: PlannerConfig):
        """Initialize the context with the required services."""
        self.git_service = git_service
        self.config = config
        self.initial_commit: Optional[str] = None

    def __enter__(self):
        """Set up the execution context, capturing the initial git commit hash."""
        if self.git_service.is_git_repo():
            try:
                self.initial_commit = self.git_service.get_current_commit()
            except Exception as e:
                log.warning(f"Could not get current commit for rollback: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up and handle rollback on failure."""
        if exc_type and self.initial_commit and self.config.rollback_on_failure:
            log.warning("Rolling back to initial state due to failure")
            try:
                self.git_service.reset_to_commit(self.initial_commit)
            except Exception as e:
                log.error(f"Failed to rollback: {e}")
