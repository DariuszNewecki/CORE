# src/features/self_healing/test_target_analyzer.py
"""
Analyzes Python source files to identify and classify functions as test targets.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from radon.visitors import ComplexityVisitor

Classification = Literal["SIMPLE", "COMPLEX"]


@dataclass
# ID: 4be9923d-aa4d-4fc6-83ff-1bc1c1918f09
class TestTarget:
    """Represents a potential function to be tested."""

    name: str
    complexity: int
    classification: Classification
    reason: str


# ID: e1e93bfa-852d-4673-85e3-ffc827419c8c
class TestTargetAnalyzer:
    """Analyzes a Python file and classifies its functions for testability."""

    def __init__(self, complexity_threshold: int = 5):
        self.complexity_threshold = complexity_threshold
        self.complex_arg_types = {"CoreContext", "AsyncSession"}
        self.io_imports = {"httpx", "sqlalchemy", "get_session"}

    # ID: f268fe3a-a735-46bc-8438-b0197dcbca8f
    def analyze_file(self, file_path: Path) -> list[TestTarget]:
        """
        Analyzes a single Python file and returns a list of classified test targets.
        """
        try:
            content = file_path.read_text("utf-8")
            tree = ast.parse(content)
            complexity_visitor = ComplexityVisitor.from_code(content)
        except Exception:
            return []

        imports = self._get_imports(tree)
        targets = []

        for func in complexity_visitor.functions:
            is_public = not func.name.startswith("_")
            if not is_public:
                continue

            node = self._find_func_node(tree, func.name)
            if not node:
                continue

            classification, reason = self._classify_function(func, node, imports)
            targets.append(
                TestTarget(
                    name=func.name,
                    complexity=func.complexity,
                    classification=classification,
                    reason=reason,
                )
            )

        return sorted(targets, key=lambda t: t.complexity)

    def _get_imports(self, tree: ast.AST) -> set[str]:
        """Extracts top-level import names from an AST."""
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        return imports

    def _find_func_node(
        self, tree: ast.AST, func_name: str
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Finds the AST node for a function by name."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    return node
        return None

    def _classify_function(
        self,
        func_metrics,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_imports: set[str],
    ) -> tuple[Classification, str]:
        """Applies heuristics to classify a function as SIMPLE or COMPLEX."""
        if func_metrics.complexity > self.complexity_threshold:
            return "COMPLEX", f"High complexity ({func_metrics.complexity})"

        for arg in node.args.args:
            if arg.annotation and isinstance(arg.annotation, ast.Name):
                if arg.annotation.id in self.complex_arg_types:
                    return "COMPLEX", f"Depends on complex type '{arg.annotation.id}'"

        if self.io_imports.intersection(file_imports):
            return "COMPLEX", "File involves I/O operations"

        return "SIMPLE", "Low complexity, no complex dependencies"
