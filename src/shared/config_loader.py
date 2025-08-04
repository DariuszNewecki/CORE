# src/shared/config_loader.py

import json
import yaml
from pathlib import Path
from typing import Dict, Any

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
        print(f"⚠️ Warning: File not found at {file_path}")
        return {}

    # Determine file type if 'auto'
    if file_type == "auto":
        suffix = file_path.suffix.lower()
        file_type = "json" if suffix == ".json" else "yaml" if suffix in (".yaml", ".yml") else None

    if file_type not in ("json", "yaml"):
        print(f"❌ Error: Unsupported file type for {file_path}")
        return {}

    try:
        with file_path.open(encoding="utf-8") as f:
            if file_type == "json":
                data = json.load(f)
                # Ensure dictionary for JSON
                return data if isinstance(data, dict) else {}
            else:  # yaml
                data = yaml.safe_load(f)
                # Ensure dictionary for YAML
                return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        print(f"❌ Error parsing {file_path}: {e}")
        return {}