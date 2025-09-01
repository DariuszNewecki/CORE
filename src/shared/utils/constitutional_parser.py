# src/shared/utils/constitutional_parser.py
"""
Parses the constitutional structure definition from meta.yaml to discover all declared file paths.
Provides the single, authoritative source for interpreting the structure
of the constitution as defined in .intent/meta.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Set

import yaml


# CAPABILITY: system.constitution.discover_files
def get_all_constitutional_paths(intent_dir: Path) -> Set[str]:
    """
    Reads meta.yaml and recursively discovers all declared constitutional file paths.
    Returns a set of repo-relative paths (e.g., '.intent/policies/safety.yaml').
    """
    meta_path = intent_dir / "meta.yaml"
    if not meta_path.exists():
        return set()

    meta_content = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    known_paths: Set[str] = {".intent/meta.yaml"}

    def _recursive_find(data: Any):
        """Recursively traverses nested data structures (dicts/lists) to find string values containing '/' and '.', adding formatted '.intent/' prefixed paths to the known_paths set."""
        if isinstance(data, dict):
            for value in data.values():
                _recursive_find(value)
        elif isinstance(data, list):
            for item in data:
                _recursive_find(item)
        elif isinstance(data, str) and "/" in data and "." in data:
            # Heuristic for finding file paths
            path_str = str(Path(".intent") / data).replace("\\", "/")
            known_paths.add(path_str)

    _recursive_find(meta_content)
    return known_paths
