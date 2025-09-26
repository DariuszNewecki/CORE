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


# ID: 5b756179-08dd-462c-ae83-2d8d02f506ac
def get_all_constitutional_paths(intent_dir: Path) -> Set[str]:
    """
    Reads meta.yaml and recursively discovers all declared constitutional file paths.
    Returns a set of repo-relative paths (e.g., '.intent/charter/policies/safety_policy.yaml').
    """
    meta_path = intent_dir / "meta.yaml"
    if not meta_path.exists():
        return set()

    meta_content = yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    # --- THIS IS THE FIX ---
    # The base path is now the repo root, not '.intent/'
    repo_root = intent_dir.parent
    known_paths: Set[str] = {str(meta_path.relative_to(repo_root))}
    # --- END OF FIX ---

    def _recursive_find(data: Any, current_prefix: str):
        if isinstance(data, dict):
            for key, value in data.items():
                _recursive_find(
                    value,
                    (
                        f"{current_prefix}/{key}"
                        if key
                        not in [
                            "charter",
                            "mind",
                            "meta_governance",
                            "derived_artifacts",
                        ]
                        else current_prefix
                    ),
                )
        elif isinstance(data, list):
            for item in data:
                _recursive_find(item, current_prefix)
        elif isinstance(data, str) and (
            data.endswith((".yaml", ".md", ".json", ".prompt", ".key"))
            or data == "charter/constitution/ACTIVE"
        ):
            # Construct path relative to repo root
            path_str = data
            if not path_str.startswith(".intent"):
                # This logic ensures paths are built correctly from meta.yaml structure
                base_dir = (
                    "charter"
                    if "charter" in current_prefix
                    else "mind" if "mind" in current_prefix else ""
                )
                if base_dir:
                    path_str = str(Path(base_dir) / data.split("/", 1)[-1])

            full_path_str = str(Path(".intent") / path_str)
            known_paths.add(full_path_str.replace("\\", "/"))

    _recursive_find(meta_content, "")
    return known_paths
