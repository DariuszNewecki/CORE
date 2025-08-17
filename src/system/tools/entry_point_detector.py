# src/system/tools/entry_point_detector.py
"""
Detects entry points in Python code (FastAPI routes, CLI commands, etc.).
"""
import ast
from pathlib import Path
from typing import Optional, Set

from shared.config_loader import load_config
from shared.logger import getLogger
from system.tools.ast_utils import is_fastapi_assignment, is_main_block
from system.tools.ast_visitor import FunctionCallVisitor

log = getLogger(__name__)


class EntryPointDetector:
    """Detects various types of entry points in Python code."""

    def __init__(self, root_path: Path, cli_entry_points: Set[str]):
        """Initialize the instance with root path, CLI entry points, and load patterns."""
        self.root_path = root_path
        self.cli_entry_points = cli_entry_points
        self.fastapi_app_name: Optional[str] = None
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> list:
        """Loads entry point detection patterns from the intent file."""
        patterns_path = self.root_path / ".intent/knowledge/entry_point_patterns.yaml"
        if not patterns_path.exists():
            log.warning("entry_point_patterns.yaml not found.")
            return []
        config = load_config(patterns_path, "yaml")
        return config.get("patterns", []) if config else []

    def detect_in_tree(self, tree: ast.AST) -> Set[str]:
        """Detect entry points in an AST tree and update internal state."""
        main_block_entries = set()

        for node in ast.walk(tree):
            if is_fastapi_assignment(node):
                self.fastapi_app_name = node.targets[0].id
            elif is_main_block(node):
                visitor = FunctionCallVisitor()
                visitor.visit(node)
                main_block_entries.update(visitor.calls)

        return main_block_entries

    def _is_fastapi_route_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator is a FastAPI route decorator."""
        return (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == self.fastapi_app_name
        )

    def get_entry_point_type(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Optional[str]:
        """Identifies decorator or CLI-based entry points for a function."""
        for decorator in node.decorator_list:
            if self._is_fastapi_route_decorator(decorator):
                return f"fastapi_route_{decorator.func.attr}"
            elif (
                isinstance(decorator, ast.Name)
                and decorator.id == "asynccontextmanager"
            ):
                return "context_manager"

        if self.fastapi_app_name and node.name == "lifespan":
            return "fastapi_lifespan"
        if node.name in self.cli_entry_points:
            return "cli_entry_point"
        return None
