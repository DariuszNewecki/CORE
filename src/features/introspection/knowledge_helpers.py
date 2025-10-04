# src/features/introspection/knowledge_helpers.py
"""
Helper utilities for knowledge graph vectorization:
- extract_source_code
- collect_vectorization_tasks (chunk-based diffing)
- reporting helpers (log_failure)
"""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path
from typing import Dict, Optional

from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text, sha256_hex

log = getLogger("core_admin.knowledge.helpers")


# ID: 8eedaa86-01be-461c-a3b1-a3a61716fefc
def extract_source_code(repo_root: Path, symbol_data: dict) -> str | None:
    """
    Extracts the source code for a symbol using AST, which is more reliable
    than line numbers. This is the single, canonical implementation.
    """
    # --- THIS IS THE FIX ---
    # The database stores a 'module' path (e.g., 'api.v1.knowledge_routes').
    # We must convert this back into a file system path.
    file_path_from_module = symbol_data.get("file_path")
    if not file_path_from_module:
        return None

    # Convert module path to file system path
    file_system_path_str = "src/" + file_path_from_module.replace(".", "/") + ".py"
    file_path = repo_root / file_system_path_str
    # --- END OF FIX ---

    symbol_path_str = symbol_data.get("symbol_path")

    if not file_path.exists():
        log.warning(
            f"Source file not found for symbol {symbol_path_str} at expected path {file_path}"
        )
        return None

    symbol_name = symbol_path_str.split("::")[-1]

    try:
        content = file_path.read_text("utf-8")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # This needs to handle nested classes/functions if symbol_path includes them
                # For now, we assume simple names.
                current_symbol_name = getattr(node, "name", None)
                if current_symbol_name == symbol_name:
                    return ast.get_source_segment(content, node)
    except Exception as e:
        log.warning(
            f"AST parsing failed for {file_path} while seeking {symbol_name}: {e}"
        )
        return None

    return None


# ID: 538af724-9c5b-4720-b3bf-964be836b2de
def log_failure(failure_log_path: Path, key: str, message: str, category: str) -> None:
    """Append a failure line to the given log file path. Ensures parent exists."""
    failure_log_path.parent.mkdir(parents=True, exist_ok=True)
    with failure_log_path.open("a", encoding="utf-8") as f:
        f.write(f"{category}\t{key}\t{message}\n")


# ID: d7880ea9-b988-4ba6-8358-b41636c0b43b
def collect_vectorization_tasks(
    symbols_map: dict,
    stored_chunks: Dict[str, dict],
    repo_root: Path,
    target: Optional[str] = None,
    force_recompute: bool = False,
    respect_model_revision: bool = True,
) -> list[dict]:
    """
    Build tasks for chunks. If `force_recompute` is True, it includes all targeted chunks
    regardless of their hash.
    """
    tasks: list[dict] = []

    for symbol_key, symbol_data in symbols_map.items():
        cap_key = symbol_data.get("capability")
        if not cap_key or cap_key == "unassigned":
            continue

        if target:
            is_match = fnmatch.fnmatch(symbol_key, target) or fnmatch.fnmatch(
                cap_key, target
            )
            if not is_match:
                continue

        if force_recompute:
            tasks.append(
                {"cap_key": cap_key, "symbol_key": symbol_key, "action": "vectorize"}
            )
            continue

        try:
            source_code = extract_source_code(repo_root, symbol_data)
            normalized_code = normalize_text(source_code)
            current_hash = sha256_hex(normalized_code)
        except Exception as e:
            log.warning(f"Could not compute hash for '{symbol_key}': {e}")
            current_hash = None

        stored = stored_chunks.get(symbol_key)
        up_to_date = False
        if stored and stored.get("hash") and current_hash:
            if respect_model_revision:
                up_to_date = stored["hash"] == current_hash and stored.get(
                    "rev"
                ) == symbol_data.get("model_revision")
            else:
                up_to_date = stored["hash"] == current_hash

        if up_to_date:
            continue

        tasks.append(
            {"cap_key": cap_key, "symbol_key": symbol_key, "action": "vectorize"}
        )

    return tasks
