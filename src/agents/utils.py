# src/agents/utils.py
"""
Utility classes and functions for CORE agents.
"""
import ast
from pathlib import Path
from typing import Optional

from shared.logger import getLogger

log = getLogger(__name__)

class SymbolLocator:
    """Dedicated class for finding symbols in code files."""
    
    @staticmethod
    def find_symbol_line(file_path: Path, symbol_name: str) -> Optional[int]:
        """Finds the line number of a function or class definition in a file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            code = file_path.read_text(encoding='utf-8')
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == symbol_name:
                        return node.lineno
        except (SyntaxError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Failed to parse {file_path}: {e}")
        return None

class PlanExecutionContext:
    """Context manager for safe plan execution with rollback."""
    
    def __init__(self, planner_agent):
        """Initializes the context with a reference to the calling agent."""
        self.planner = planner_agent
        self.initial_commit = None
        
    def __enter__(self):
        """Sets up the execution context, capturing the initial git commit hash."""
        if self.planner.git_service.is_git_repo():
            try:
                self.initial_commit = self.planner.git_service.get_current_commit()
            except Exception as e:
                log.warning(f"Could not get current commit for rollback: {e}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleans up and handles rollback on failure."""
        if exc_type and self.initial_commit and self.planner.config.rollback_on_failure:
            log.warning("Rolling back to initial state due to failure")
            try:
                self.planner.git_service.reset_to_commit(self.initial_commit)
            except Exception as e:
                log.error(f"Failed to rollback: {e}")