# src/shared/config_loader.py
"""
Loads JSON or YAML configuration files into dictionaries with consistent error handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: config.load
def load_config(file_path: Path, file_type: str = "auto") -> Dict[str, Any]:
    """
    Loads a JSON or YAML file into a dictionary with consistent error handling.

    Args:
        file_path (Path): Path to the file to load.
        file_type (str): 'json', 'yaml', or 'auto' to infer from extension.

    Returns:
        Dict[str, Any]: Parsed file content or empty dict if file is missing/invalid.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        log.warning(
            f"Configuration file not found at {file_path}, returning empty dict."
        )
        return {}

    # Determine file type if 'auto'
    if file_type == "auto":
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            file_type = "json"
        elif suffix in (".yaml", ".yml"):
            file_type = "yaml"
        else:
            log.error(
                f"Cannot determine file type from extension '{suffix}' for {file_path}"
            )
            return {}

    if file_type not in ("json", "yaml"):
        log.error(f"Unsupported file type '{file_type}' for {file_path}")
        return {}

    try:
        with file_path.open(encoding="utf-8") as f:
            if file_type == "json":
                data = json.load(f)
            else:  # yaml
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                log.warning(
                    f"File {file_path} does not contain a dictionary, returning empty dict."
                )
                return {}

            return data

    except (json.JSONDecodeError, yaml.YAMLError) as e:
        log.error(f"Error parsing {file_path}: {e}")
        return {}
    except (OSError, IOError) as e:
        log.error(f"Error reading file {file_path}: {e}")
        return {}
