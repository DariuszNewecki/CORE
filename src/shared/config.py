# src/shared/config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger

log = getLogger("core.config")

REPO_ROOT = Path(__file__).resolve().parents[2]


# ID: 07a85609-ecab-4168-a4dd-dc9112f974d3
class Settings(BaseSettings):
    """
    The single, canonical source of truth for all CORE configuration.
    It loads from environment variables and provides "Pathfinder" methods
    to access constitutional files via the .intent/meta.yaml index.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow", case_sensitive=True
    )

    _meta_config: Dict[str, Any] = PrivateAttr(default_factory=dict)

    REPO_PATH: Path = REPO_ROOT
    MIND: Path = REPO_PATH / ".intent"
    BODY: Path = REPO_PATH / "src"
    LLM_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    CORE_MAX_CONCURRENT_REQUESTS: int = 5

    DATABASE_URL: str
    QDRANT_URL: str
    QDRANT_COLLECTION_NAME: str = "core_capabilities"

    LOCAL_EMBEDDING_API_URL: str
    LOCAL_EMBEDDING_MODEL_NAME: str
    LOCAL_EMBEDDING_DIM: int
    LOCAL_EMBEDDING_API_KEY: Optional[str] = None
    EMBED_MODEL_REVISION: str = "2025-09-15"

    # --- THIS IS THE FIX ---
    # Formally declare KEY_STORAGE_DIR with its correct type and a default value.
    # Pydantic will now automatically handle loading from .env and casting to a Path object.
    KEY_STORAGE_DIR: Path = REPO_PATH / ".intent" / "keys"
    # --- END OF FIX ---

    def __init__(self, **values: Any):
        super().__init__(**values)
        self._load_meta_config()

    def _load_meta_config(self):
        """Loads and caches the .intent/meta.yaml file, failing loudly if invalid."""
        meta_path = self.REPO_PATH / ".intent" / "meta.yaml"
        if not meta_path.exists():
            raise FileNotFoundError("FATAL: .intent/meta.yaml is missing.")
        try:
            self._meta_config = self._load_file_content(meta_path)
        except (IOError, ValueError) as e:
            raise RuntimeError(f"FATAL: Could not parse .intent/meta.yaml: {e}")

    def _load_file_content(self, file_path: Path) -> Dict[str, Any]:
        """Internal, unified loader for YAML or JSON files."""
        content = file_path.read_text("utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif file_path.suffix == ".json":
            return json.loads(content) or {}
        raise ValueError(f"Unsupported config file type: {file_path}")

    # ID: 8e9be503-e7c9-4afb-a6a5-385750ec91cf
    def get_path(self, logical_path: str) -> Path:
        """
        Gets the absolute path to a constitutional file using its logical,
        dot-notation path from meta.yaml.
        """
        keys = logical_path.split(".")
        value = self._meta_config
        try:
            for key in keys:
                value = value[key]
            if not isinstance(value, str):
                raise TypeError
            # Paths in meta.yaml are relative to the .intent directory
            return self.MIND / value
        except (KeyError, TypeError):
            raise FileNotFoundError(
                f"Logical path '{logical_path}' not found or invalid in meta.yaml."
            )

    # ID: b1c2d3e4-f5a6-b7c8-d9e0-f1a2b3c4d5e6
    def find_logical_path_for_file(self, filename: str) -> str:
        """
        Searches the meta.yaml index to find the full relative path for a given filename.
        """

        def _search_dict(d: Any) -> Optional[str]:
            if isinstance(d, dict):
                for key, value in d.items():
                    if isinstance(value, str) and value.endswith(filename):
                        return value
                    found = _search_dict(value)
                    if found:
                        return found
            return None

        found_path = _search_dict(self._meta_config)
        if found_path:
            return found_path
        raise ValueError(f"Filename '{filename}' not found in meta.yaml index.")

    # ID: 08272f29-c9c9-4c54-8253-b7fea9938050
    def load(self, logical_path: str) -> Dict[str, Any]:
        """
        Loads and parses a constitutional YAML/JSON file using its logical path.
        """
        file_path = self.get_path(logical_path)
        try:
            return self._load_file_content(file_path)
        except FileNotFoundError:
            log.error(
                f"File for logical path '{logical_path}' not found at expected location: {file_path}"
            )
            raise
        except (IOError, ValueError) as e:
            raise IOError(f"Failed to load or parse file for '{logical_path}': {e}")


try:
    settings = Settings()
except (RuntimeError, FileNotFoundError) as e:
    log.critical(f"FATAL ERROR during settings initialization: {e}")
    raise
