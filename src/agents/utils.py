# src/agents/utils.py
"""
Utility classes and functions for CORE agents.
"""
import ast
import textwrap
from pathlib import Path
from typing import Optional, Tuple

# --- THIS IS THE FIX: ADD MISSING IMPORTS ---
from agents.models import PlannerConfig
from core.git_service import GitService
from shared.logger import getLogger

log = getLogger(__name__)


class CodeEditor:
    """Provides capabilities to surgically edit code files."""

    def _get_symbol_start_end_lines(
        self, tree: ast.AST, symbol_name: str
    ) -> Optional[Tuple[int, int]]:
        """Finds the 1-based start and end line numbers of a symbol."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    if hasattr(node, "end_lineno") and node.end_lineno is not None:
                        return node.lineno, node.end_lineno
        return None

    def replace_symbol_in_code(
        self, original_code: str, symbol_name: str, new_code_str: str
    ) -> str:
        """
        Replaces a function/method in code with a new version using a line-based strategy.
        """
        try:
            original_tree = ast.parse(original_code)
        except SyntaxError as e:
            raise ValueError(f"Could not parse original code due to syntax error: {e}")

        symbol_location = self._get_symbol_start_end_lines(original_tree, symbol_name)
        if not symbol_location:
            raise ValueError(f"Symbol '{symbol_name}' not found in the original code.")

        start_line, end_line = symbol_location
        start_index = start_line - 1
        end_index = end_line

        lines = original_code.splitlines()

        original_line = lines[start_index]
        indentation = len(original_line) - len(original_line.lstrip(" "))

        clean_new_code = textwrap.dedent(new_code_str).strip()
        new_code_lines = clean_new_code.splitlines()
        indented_new_code_lines = [
            f"{' ' * indentation}{line}" for line in new_code_lines
        ]

        code_before = lines[:start_index]
        code_after = lines[end_index:]

        final_lines = code_before + indented_new_code_lines + code_after
        return "\n".join(final_lines)


class SymbolLocator:
    """Dedicated class for finding symbols in code files."""

    @staticmethod
    def find_symbol_line(file_path: Path, symbol_name: str) -> Optional[int]:
        """Finds the line number of a function or class definition in a file."""
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
            raise RuntimeError(f"Failed to parse {file_path}: {e}")
        return None


class PlanExecutionContext:
    """Context manager for safe plan execution with rollback."""

    def __init__(self, git_service: GitService, config: PlannerConfig):
        """Initializes the context with the required services."""
        self.git_service = git_service
        self.config = config
        self.initial_commit = None

    def __enter__(self):
        """Sets up the execution context, capturing the initial git commit hash."""
        if self.git_service.is_git_repo():
            try:
                self.initial_commit = self.git_service.get_current_commit()
            except Exception as e:
                log.warning(f"Could not get current commit for rollback: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleans up and handles rollback on failure."""
        if exc_type and self.initial_commit and self.config.rollback_on_failure:
            log.warning("Rolling back to initial state due to failure")
            try:
                self.git_service.reset_to_commit(self.initial_commit)
            except Exception as e:
                log.error(f"Failed to rollback: {e}")