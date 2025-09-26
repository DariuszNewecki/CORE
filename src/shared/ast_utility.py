# src/shared/ast_utility.py
"""
Utility functions for working with Python AST (Abstract Syntax Trees).

Provides helpers to parse, inspect, and analyze Python source code at the
AST level. Includes visitors for extracting function calls, base classes,
docstrings, parameters, metadata tags, and a robust structural hash that is
insensitive to docstrings and whitespace.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


# --- THIS IS THE NEW, ROBUST HELPER FUNCTION ---
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
def find_definition_line(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, source_lines: List[str]
) -> int:
    """
    Finds the actual line number of the 'def' or 'class' keyword,
    skipping over any decorators.
    """
    if not node.decorator_list:
        return node.lineno

    # The line number of the last decorator
    last_decorator_line = (
        node.decorator_list[-1].end_lineno or node.decorator_list[-1].lineno
    )

    # Search for "def" or "class" from the last decorator onwards
    for i in range(last_decorator_line, len(source_lines)):
        line = source_lines[i].strip()
        if (
            line.startswith(f"def {node.name}")
            or line.startswith(f"async def {node.name}")
            or line.startswith(f"class {node.name}")
        ):
            return i + 1  # Return 1-based line number

    return node.lineno  # Fallback


# --- END OF NEW HELPER FUNCTION ---


# ---------------------------------------------------------------------------
# Basic extractors
# ---------------------------------------------------------------------------


# ID: 79ccf26e-3710-4802-9ccb-29423f545e45
def extract_docstring(node: ast.AST) -> Optional[str]:
    """Extract the docstring from the given AST node if it exists."""
    return ast.get_docstring(node)


# ID: 79024211-279d-40af-91c3-679d5afdcf9f
def extract_base_classes(node: ast.ClassDef) -> List[str]:
    """Return a list of base class names for the given class node."""
    bases: List[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            # e.g. module.Class — capture best-effort dotted path
            left = None
            if isinstance(base.value, ast.Name):
                left = base.value.id
            elif isinstance(base.value, ast.Attribute):
                # fallback: last attribute segment
                left = base.value.attr
            bases.append(f"{left}.{base.attr}" if left else base.attr)
    return bases


# ID: 502f4096-53ca-49d8-b3e4-ec7a075b0881
def extract_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """Extract parameter names from a function (or async function) definition node."""
    if not hasattr(node, "args") or node.args is None:
        return []
    return [arg.arg for arg in getattr(node.args, "args", [])]


# ID: d73a2936-68f4-4dc4-b6ef-db6188740683
class FunctionCallVisitor(ast.NodeVisitor):
    """Visitor that collects function call names within a node."""

    def __init__(self) -> None:
        """Initialize an empty collection of function call names."""
        self.calls: List[str] = []

    # ID: 2eec3148-6aeb-4d74-9dd3-b73be105ee02
    def visit_Call(self, node: ast.Call) -> None:
        """Record the called function/method name, then continue traversal."""
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Metadata parsing (used by knowledge discovery)
# ---------------------------------------------------------------------------


# ID: 5f4a3e52-b52a-49ac-aa37-a5201376979f
def parse_metadata_comment(node: ast.AST, source_lines: List[str]) -> Dict[str, str]:
    """Returns a dict like {'capability': 'domain.key'} when present; otherwise empty dict."""
    if getattr(node, "lineno", None) and node.lineno > 1:
        line = source_lines[node.lineno - 2].strip()
        if line.startswith("#") and "CAPABILITY:" in line.upper():
            try:
                # split on the first colon to preserve values containing colons
                prefix, value = line.split(":", 1)
                return {"capability": value.strip()}
            except ValueError:
                pass
    return {}


# ---------------------------------------------------------------------------
# Structural hashing (canonical implementation lives here)
# ---------------------------------------------------------------------------


def _strip_docstrings(node: ast.AST) -> ast.AST:
    """Remove leading docstring expressions from modules/classes/functions."""
    if isinstance(
        node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        if (
            getattr(node, "body", None)
            and len(node.body) > 0
            and isinstance(node.body[0], ast.Expr)
            and isinstance(getattr(node.body[0], "value", None), ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]

    for child in ast.iter_child_nodes(node):
        _strip_docstrings(child)

    return node


# ID: 1b0ec762-579f-4b3d-93eb-c88e42253c54
def calculate_structural_hash(node: ast.AST) -> str:
    """Calculate a stable structural hash for an AST node.

    The hash is:
      - insensitive to docstrings (they are stripped)
      - insensitive to whitespace and newlines
    """
    try:
        normalized = ast.parse(ast.unparse(node))
        normalized = _strip_docstrings(normalized)
        structural = ast.unparse(normalized).replace("\n", "").replace(" ", "")
        return hashlib.sha256(structural.encode("utf-8")).hexdigest()
    except Exception:
        # Fallback: never block callers on hashing
        try:
            fallback = ast.unparse(node)
        except Exception:
            fallback = repr(node)
        log.exception("Structural hash computation failed; using fallback hash.")
        return hashlib.sha256(fallback.encode("utf-8")).hexdigest()
