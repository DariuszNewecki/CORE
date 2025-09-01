# src/system/tools/entry_point_detector.py
"""
Provides AST-based detection and classification of Python entry points including CLI commands, FastAPI routes, and main block function calls.
"""

from __future__ import annotations

import ast
from typing import Optional, Set

from system.tools.config.builder_config import BuilderConfig


# CAPABILITY: tooling.entry_point.detect
class EntryPointDetector:
    """Detects various types of entry points (CLI, FastAPI, etc.)."""

    # CAPABILITY: tooling.entry_point_detector.initialize
    def __init__(self, config: BuilderConfig):
        """Initializes the EntryPointDetector with the builder configuration."""
        self.cli_entry_points = config.cli_entry_points.copy()
        self.fastapi_app_name: Optional[str] = None

    # CAPABILITY: tooling.ast.detect_fastapi_app
    def detect_fastapi_app_name(self, tree: ast.AST) -> None:
        """Scan AST tree to find FastAPI app instance name."""
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "FastAPI"
                and isinstance(node.targets[0], ast.Name)
            ):
                self.fastapi_app_name = node.targets[0].id
                break

    # CAPABILITY: tooling.entry_point.detect_main_calls
    def detect_main_block_calls(self, tree: ast.AST) -> Set[str]:
        """Find function calls in if __name__ == '__main__' blocks."""
        main_block_entries = set()

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"
            ):
                from system.tools.ast_visitor import FunctionCallVisitor

                visitor = FunctionCallVisitor()
                visitor.visit(node)
                main_block_entries.update(visitor.calls)

        return main_block_entries

    # CAPABILITY: tooling.cli.update_entry_points
    def update_cli_entry_points(self, additional_points: Set[str]) -> None:
        """Add newly discovered CLI entry points."""
        self.cli_entry_points.update(additional_points)

    # CAPABILITY: tooling.entry_point.detect_type
    def get_entry_point_type(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Optional[str]:
        """Identify decorator or CLI-based entry points for a function."""
        # Check decorators for FastAPI routes
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == self.fastapi_app_name
            ):
                return f"fastapi_route_{decorator.func.attr}"
            elif (
                isinstance(decorator, ast.Name)
                and decorator.id == "asynccontextmanager"
            ):
                return "context_manager"

        # Check for FastAPI lifespan
        if self.fastapi_app_name and node.name == "lifespan":
            return "fastapi_lifespan"

        # Check for CLI entry points
        if node.name in self.cli_entry_points:
            return "cli_entry_point"

        return None
