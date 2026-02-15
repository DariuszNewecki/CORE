# src/features/self_healing/knowledge_consolidation_service.py
"""
Provides services for identifying and consolidating duplicated or common knowledge
across the codebase, serving the 'dry_by_design' principle.
"""

from __future__ import annotations

import ast
import hashlib

# --- THIS IS THE FIX ---
from shared.ast_utility import normalize_ast
from shared.config import settings


# --- END OF FIX ---


# ID: e9a1b8c3-d7f4-4b1e-a9d5-f8c3d7f4b1e9
def find_structurally_similar_helpers(
    min_occurrences: int = 3,
    max_lines: int = 10,
) -> dict[str, list[tuple[str, int]]]:
    """
    Scans the 'src/' directory for small, structurally identical public functions.

    It works by creating a normalized Abstract Syntax Tree (AST) for each function,
    hashing it, and grouping functions by their hash. This allows it to find
    functionally identical helpers even if variable names and docstrings differ.

    Args:
        min_occurrences: The minimum number of times a function must appear to be considered a duplicate.
        max_lines: The maximum number of lines a function can have to be considered a small helper.

    Returns:
        A dictionary where keys are the structural hash of duplicated functions
        and values are a list of tuples containing (file_path, line_number).
    """
    src_root = settings.REPO_PATH / "src"
    duplicates: dict[str, list[tuple[str, int]]] = {}

    for py_file in src_root.rglob("*.py"):
        # Exclude tests and other non-source directories
        if "test" in py_file.parts or "venv" in py_file.parts:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and len(node.body) <= max_lines
                and not node.name.startswith("_")
                and not node.decorator_list
            ):
                try:
                    # Normalize the AST to make the hash independent of var names and docstrings
                    norm_ast_str = normalize_ast(node)
                    h = hashlib.sha256(norm_ast_str.encode()).hexdigest()
                    rel_path = str(py_file.relative_to(settings.REPO_PATH))
                    duplicates.setdefault(h, []).append((rel_path, node.lineno))
                except Exception:
                    continue  # Skip nodes that fail normalization

    # Filter for groups that meet the minimum occurrence threshold
    return {
        h: places for h, places in duplicates.items() if len(places) >= min_occurrences
    }
