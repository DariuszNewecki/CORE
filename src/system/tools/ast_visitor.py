# src/system/tools/ast_visitor.py
"""
Provides specialized AST visitors for the KnowledgeGraphBuilder to separate tree traversal logic from main orchestration.
"""

from __future__ import annotations

# src/system/tools/ast_visitor.py
"""
Contains specialized AST (Abstract Syntax Tree) visitors for the
KnowledgeGraphBuilder. This module separates the complex logic of tree
traversal from the main orchestration logic of the builder.
"""
import ast
from pathlib import Path
from typing import List


class FunctionCallVisitor(ast.NodeVisitor):
    """An AST visitor that collects the names of all functions being called within a node."""

    def __init__(self):
        self.calls: set[str] = set()

    def visit_Call(self, node: ast.Call):
        """Records function or method calls in `self.calls` and recursively visits child nodes."""
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
        self.generic_visit(node)


class ContextAwareVisitor(ast.NodeVisitor):
    """A stateful AST visitor that understands nested class and function contexts."""

    def __init__(self, builder, filepath: Path, source_lines: List[str]):
        """Initialize the instance with the given builder, filepath, source lines, and an empty context stack."""
        self.builder = builder
        self.filepath = filepath
        self.source_lines = source_lines
        self.context_stack: List[str] = []

    def _process_and_visit(self, node, node_type: str):
        """Helper to process a symbol and manage the context stack."""
        parent_key = self.context_stack[-1] if self.context_stack else None

        is_method = False
        if parent_key and parent_key in self.builder.functions:
            if self.builder.functions[parent_key].is_class:
                is_method = True

        symbol_key = self.builder._process_symbol_node(
            node, self.filepath, self.source_lines, parent_key if is_method else None
        )

        if symbol_key:
            self.context_stack.append(symbol_key)
            self.generic_visit(node)
            self.context_stack.pop()
        else:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Processes a class definition node, and visits its children."""
        self._process_and_visit(node, "ClassDef")

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Processes a function definition node, and visits its children."""
        self._process_and_visit(node, "FunctionDef")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Processes an async function definition node, and visits its children."""
        self._process_and_visit(node, "AsyncFunctionDef")
