# src/system/tools/ast_utils.py
"""
Provides utilities for analyzing and manipulating Python abstract syntax trees (ASTs) for documentation and structural analysis.
"""

from __future__ import annotations

import ast
import hashlib
import re
from typing import Dict, List, Optional


# CAPABILITY: tooling.ast.strip_docstrings
def strip_docstrings(node: ast.AST) -> ast.AST:
    """Recursively remove docstring nodes from an AST tree for structural hashing."""
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
    ):
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]

    for child_node in ast.iter_child_nodes(node):
        strip_docstrings(child_node)

    return node


# CAPABILITY: tooling.ast.detect_docstring
def detect_docstring(node: ast.AST) -> Optional[str]:
    """Detect both standard and non-standard docstrings for a node."""
    # Try standard docstring first
    standard_doc = ast.get_docstring(node)
    if standard_doc:
        return standard_doc

    # Check for non-standard docstrings
    if (
        hasattr(node, "body")
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value

    return None


# CAPABILITY: tooling.ast.calculate_structural_hash
def calculate_structural_hash(node: ast.AST) -> str:
    """Calculate a hash for structural comparison of AST nodes."""
    node_for_hashing = strip_docstrings(ast.parse(ast.unparse(node)))
    structural_string = ast.unparse(node_for_hashing).replace("\n", "").replace(" ", "")
    return hashlib.sha256(structural_string.encode("utf-8")).hexdigest()


# CAPABILITY: tooling.ast.parse_capability_metadata
def parse_metadata_comment(node: ast.AST, source_lines: List[str]) -> Dict[str, str]:
    """Parse the line immediately preceding a symbol definition for a '# CAPABILITY:' tag."""
    if node.lineno > 1:
        line = source_lines[node.lineno - 2].strip()
        if line.startswith("#"):
            match = re.search(r"CAPABILITY:\s*(\S+)", line, re.IGNORECASE)
            if match:
                return {"capability": match.group(1).strip()}
    return {}


# CAPABILITY: tooling.ast.extract_base_classes
def extract_base_classes(node: ast.ClassDef) -> List[str]:
    """Extract base class names from a class definition."""
    base_classes = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            base_classes.append(base.id)
        elif isinstance(base, ast.Attribute):
            base_classes.append(base.attr)
    return base_classes


# CAPABILITY: tooling.ast.extract_function_parameters
def extract_function_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> List[str]:
    """Extract parameter names from a function definition."""
    if not hasattr(node, "args"):
        return []
    return [arg.arg for arg in node.args.args]
