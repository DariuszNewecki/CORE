# src/shared/utils/yaml_loader.py
"""
Provides utilities for loading and parsing YAML files into Python dictionaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


# CAPABILITY: yaml_loading
def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load and parse a YAML file from the given path.

    Args:
        file_path: Path to the YAML file to load

    Returns:
        Parsed YAML content as a dictionary

    Raises:
        FileNotFoundError: If the specified file doesn't exist
        yaml.YAMLError: If the YAML content is malformed
    """
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML file {file_path}: {e}")
