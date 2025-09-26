# src/shared/config_loader.py
"""
Utility for loading configuration files (YAML or JSON) safely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

from shared.logger import getLogger

log = getLogger(__name__)


# ID: 85467d87-762e-461c-8c08-af2b982e2387
def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Loads a YAML or JSON config file safely, with consistent error handling.

    Args:
        file_path: Path to the configuration file (must be .yaml, .yml, or .json).

    Returns:
        A dictionary containing the parsed configuration data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported or parsing fails.
    """
    if not file_path.exists():
        log.error(f"Config file not found: {file_path}")
        raise FileNotFoundError(f"Config file not found: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif file_path.suffix == ".json":
            return json.loads(content) or {}
        else:
            log.error(f"Unsupported file type: {file_path.suffix}")
            raise ValueError(f"Unsupported config file type: {file_path}")
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        log.error(f"Error parsing config {file_path}: {e}")
        raise ValueError(f"Invalid config format in {file_path}") from e
    except UnicodeDecodeError as e:
        log.error(f"Encoding error in {file_path}: {e}")
        raise ValueError(f"Encoding error in config {file_path}") from e
