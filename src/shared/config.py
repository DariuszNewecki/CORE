# src/shared/config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger

log = getLogger("core.config")

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    # ... add other core ENV VARS here ...

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

    # --- THIS IS THE FIX ---
    # The lru_cache decorator has been removed to prevent the TypeError.
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
            return self.MIND / value
        except (KeyError, TypeError):
            raise FileNotFoundError(
                f"Logical path '{logical_path}' not found or invalid in meta.yaml."
            )

    # --- END OF FIX ---

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
