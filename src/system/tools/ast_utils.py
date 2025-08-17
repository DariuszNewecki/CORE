# src/system/tools/ast_utils.py
"""
Utilities for parsing and analyzing AST nodes.
"""
import ast
import hashlib
import re
from typing import Dict, List, Optional


def strip_docstrings(node):
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


def calculate_structural_hash(node: ast.AST) -> str:
    """Calculate a hash of the node's structure without docstrings."""
    node_for_hashing = strip_docstrings(ast.parse(ast.unparse(node)))
    structural_string = ast.unparse(node_for_hashing).replace("\n", "").replace(" ", "")
    return hashlib.sha256(structural_string.encode("utf-8")).hexdigest()


def detect_docstring(node: ast.AST) -> Optional[str]:
    """Detects both standard and non-standard docstrings for a node."""
    standard_doc = ast.get_docstring(node)
    if standard_doc:
        return standard_doc

    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value
    return None


def extract_base_classes(node: ast.ClassDef) -> List[str]:
    """Extract base class names from a class definition."""
    base_classes = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            base_classes.append(base.id)
        elif isinstance(base, ast.Attribute):
            base_classes.append(base.attr)
    return base_classes


def parse_metadata_comment(node: ast.AST, source_lines: List[str]) -> Dict[str, str]:
    """Parses the line immediately preceding a symbol definition for a '# CAPABILITY:' tag."""
    if node.lineno > 1 and node.lineno - 2 < len(source_lines):
        line = source_lines[node.lineno - 2].strip()
        if line.startswith("#"):
            match = re.search(r"CAPABILITY:\s*(\S+)", line, re.IGNORECASE)
            if match:
                return {"capability": match.group(1).strip()}
    return {}


def is_fastapi_assignment(node: ast.AST) -> bool:
    """Check if node is a FastAPI app assignment."""
    return (
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "FastAPI"
        and isinstance(node.targets[0], ast.Name)
    )


def is_main_block(node: ast.AST) -> bool:
    """Check if node is an if __name__ == '__main__' block."""
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )
