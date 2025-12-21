# src/shared/utils/constitutional_parser.py
"""
Parses the constitutional structure definition from meta.yaml to discover all declared file paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# ID: ae492732-1dab-4982-a129-1f7f9af67439
def get_all_constitutional_paths(meta_content: dict, intent_dir: Path) -> set[str]:
    """
    Recursively discovers all declared constitutional file paths from the parsed
    content of meta.yaml.

    Args:
        meta_content: The dictionary parsed from meta.yaml.
        intent_dir: The path to the .intent directory.

    Returns:
        A set of repo-relative paths (e.g., '.intent/charter/policies/safety_policy.json').
    """
    repo_root = intent_dir.parent
    # The path to meta.yaml is known relative to the intent_dir
    known_paths: set[str] = {
        str((intent_dir / "meta.yaml").relative_to(repo_root)).replace("\\", "/")
    }

    def _recursive_find(data: Any):
        if isinstance(data, dict):
            for value in data.values():
                _recursive_find(value)
        elif isinstance(data, list):
            for item in data:
                _recursive_find(item)
        elif (
            isinstance(data, str)
            and (intent_dir.name not in data)
            and ("/" in data or "\\" in data)
        ):
            # --- THIS IS THE DEFINITIVE FIX ---
            # All paths are constructed relative to the provided intent_dir,
            # removing the hardcoded ".intent".
            full_path = intent_dir / data
            known_paths.add(str(full_path.relative_to(repo_root)).replace("\\", "/"))
            # --- END OF FIX ---

    _recursive_find(meta_content)
    return known_paths
