# src/features/introspection/knowledge_helpers.py

"""
Helper utilities for knowledge graph vectorization:
- extract_source_code
- reporting helpers (log_failure)
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1068de52-6bbb-43b9-a22c-cd2e6dc2a833
def extract_source_code(repo_root: Path, symbol_data: dict[str, Any]) -> str | None:
    """
    Extracts the source code for a symbol using its database record.
    This is the single, canonical implementation for reading symbol source.
    """
    module_path = symbol_data.get("module")
    symbol_path_str = symbol_data.get("symbol_path")
    if not module_path or not symbol_path_str:
        logger.warning(
            "Cannot extract source code: symbol data is missing 'module' or 'symbol_path'."
        )
        return None
    file_system_path_str = "src/" + module_path.replace(".", "/") + ".py"
    file_path = repo_root / file_system_path_str
    if not file_path.exists():
        logger.warning(
            "Source file not found for symbol %s at expected path %s",
            symbol_path_str,
            file_path,
        )
        return None
    symbol_name = symbol_path_str.split("::")[-1]
    try:
        content = file_path.read_text("utf-8")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                current_symbol_name = getattr(node, "name", None)
                if current_symbol_name == symbol_name:
                    return ast.get_source_segment(content, node)
    except Exception as e:
        logger.warning(
            "AST parsing failed for %s while seeking %s: %s", file_path, symbol_name, e
        )
        return None
    return None


# ID: 0bfeee2b-fe81-4abe-bb51-f2b0b6a74af9
def log_failure(failure_log_path: Path, key: str, message: str, category: str) -> None:
    """Append a failure line to the given log file path. Ensures parent exists."""
    failure_log_path.parent.mkdir(parents=True, exist_ok=True)
    with failure_log_path.open("a", encoding="utf-8") as f:
        f.write(f"{category}\t{key}\t{message}\n")
