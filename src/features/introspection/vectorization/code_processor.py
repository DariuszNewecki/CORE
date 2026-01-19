# src/features/introspection/vectorization/code_processor.py

"""AST logic for extracting source segments."""

from __future__ import annotations

import ast
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 21efc550-8ef3-48f0-82df-e7a129accd69
def extract_symbol_source(file_path: Path, symbol_path: str) -> str | None:
    """Extracts source segment of a specific symbol via AST."""
    if not file_path.exists():
        logger.warning("File missing: %s", file_path)
        return None

    content = file_path.read_text("utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
        target_name = symbol_path.split("::")[-1]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if hasattr(node, "name") and node.name == target_name:
                    return ast.get_source_segment(content, node)
    except Exception:
        return None
    return None
