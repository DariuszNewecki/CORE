# src/shared/ast_utility.py
"""
Shared utilities for AST parsing, used by builders and auditors to avoid duplication.
# CAPABILITY: ast_parsing
"""

from __future__ import annotations

import ast
import hashlib
from typing import List, Optional, Set

from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: tooling.ast.collect_function_calls
class FunctionCallVisitor(ast.NodeVisitor):
    """AST visitor to collect function calls."""

    # CAPABILITY: shared.ast.function_call_visitor.initialize
    def __init__(self):
        """Initializes the visitor with an empty set to store call names."""
        self.calls: Set[str] = set()

    # CAPABILITY: code.ast.visit_call
    def visit_Call(self, node: ast.Call):
        """Adds the function name to the set of calls and visits child nodes."""
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
        self.generic_visit(node)


# CAPABILITY: code.ast.extract_docstring
def extract_docstring(node: ast.AST) -> Optional[str]:
    """Extracts the docstring from an AST node."""
    return ast.get_docstring(node)


# CAPABILITY: tooling.ast.extract_function_parameters
def extract_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """Extracts parameter names from a function definition."""
    return [arg.arg for arg in node.args.args]


# CAPABILITY: tooling.ast.extract_base_classes
def extract_base_classes(node: ast.ClassDef) -> List[str]:
    """Extracts base class names from a class definition."""
    return [base.id if isinstance(base, ast.Name) else "" for base in node.bases]


# CAPABILITY: shared.ast.calculate_structural_hash
def calculate_structural_hash(node: ast.AST) -> str:
    """Calculates a structural hash for an AST node."""
    source = ast.unparse(node)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


# CAPABILITY: shared.ast.parse_metadata_comment
def parse_metadata_comment(node: ast.AST, lines: List[str]) -> dict:
    """Parses metadata comments above a node (e.g., # CAPABILITY:)."""
    metadata = {}
    if node.lineno > 1:
        prev_line = lines[node.lineno - 2].strip()
        if prev_line.startswith("# CAPABILITY:"):
            parts = prev_line.split(":", 1)
            if len(parts) > 1:
                metadata["capability"] = parts[1].strip()
    return metadata
