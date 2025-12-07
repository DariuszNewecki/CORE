# src/shared/config_loader.py

"""
Utility for loading configuration files (YAML or JSON) safely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 7c39612e-da89-47b1-8b80-131aeec8d4fb
def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    Loads a YAML or JSON config file safely, with consistent error handling.
    This is the single source of truth for YAML loading.

    Args:
        file_path: Path to the configuration file.

    Returns:
        A dictionary containing the parsed configuration data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported or parsing fails.
    """
    if not file_path.exists():
        logger.error("Config file not found: %s", file_path)
        raise FileNotFoundError(f"Config file not found: {file_path}")
    try:
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif file_path.suffix == ".json":
            return json.loads(content) or {}
        else:
            logger.error(f"Unsupported file type: {file_path.suffix}")
            raise ValueError(f"Unsupported config file type: {file_path}")
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        logger.error("Error parsing config {file_path}: %s", e)
        raise ValueError(f"Invalid config format in {file_path}") from e
    except UnicodeDecodeError as e:
        logger.error("Encoding error in {file_path}: %s", e)
        raise ValueError(f"Encoding error in config {file_path}") from e
