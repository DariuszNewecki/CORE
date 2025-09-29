# src/shared/config.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# --- THIS IS THE FIX ---
# We now explicitly load the .env file right here, ensuring it's always available.
from dotenv import load_dotenv
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger

log = getLogger("core.config")

REPO_ROOT = Path(__file__).resolve().parents[2]
# This line proactively loads the .env file from the project root.
load_dotenv(REPO_ROOT / ".env")
# --- END OF FIX ---


# ID: fffe6c00-5587-4951-a7c2-2dd83d1adb5f
class Settings(BaseSettings):
    """
    The single, canonical source of truth for all CORE configuration.
    It loads from environment variables and provides "Pathfinder" methods
    to access constitutional files via the .intent/meta.yaml index.
    """

    model_config = SettingsConfigDict(
        # We still keep this for pydantic's native features, but our load_dotenv is more robust.
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
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

    KEY_STORAGE_DIR: Path = REPO_PATH / ".intent" / "keys"

    def __init__(self, **values: Any):
        super().__init__(**values)
        if (self.REPO_PATH / ".intent" / "meta.yaml").exists():
            self._load_meta_config()

    # ID: ea16ad9b-bf16-4e44-bc48-dd8734f79f73
    def initialize_for_test(self, repo_path: Path):
        self.REPO_PATH = repo_path
        self.MIND = repo_path / ".intent"
        self.BODY = repo_path / "src"
        self._load_meta_config()

    def _load_meta_config(self):
        meta_path = self.REPO_PATH / ".intent" / "meta.yaml"
        if not meta_path.exists():
            self._meta_config = {}
            return
        try:
            self._meta_config = self._load_file_content(meta_path)
        except (IOError, ValueError) as e:
            raise RuntimeError(f"FATAL: Could not parse .intent/meta.yaml: {e}")

    def _load_file_content(self, file_path: Path) -> Dict[str, Any]:
        content = file_path.read_text("utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        if file_path.suffix == ".json":
            return json.loads(content) or {}
        raise ValueError(f"Unsupported config file type: {file_path}")

    # ID: 84038773-3d4c-4f59-8cf7-db6b68e0fd37
    def get_path(self, logical_path: str) -> Path:
        keys = logical_path.split(".")
        value: Any = self._meta_config
        try:
            for key in keys:
                value = value[key]
            if not isinstance(value, str):
                raise TypeError
            if value.startswith("charter/") or value.startswith("mind/"):
                return self.REPO_PATH / ".intent" / value
            return self.REPO_PATH / value
        except (KeyError, TypeError):
            raise FileNotFoundError(
                f"Logical path '{logical_path}' not found or invalid in meta.yaml."
            )

    # ID: ab774e44-9edf-4309-af2a-84a20f9e86bd
    def find_logical_path_for_file(self, filename: str) -> str:
        def _search(d: Any) -> Optional[str]:
            if isinstance(d, dict):
                for _, v in d.items():
                    if isinstance(v, str) and v.endswith(filename):
                        return v
                    found = _search(v)
                    if found:
                        return found
            return None

        found_path = _search(self._meta_config)
        if found_path:
            return found_path
        raise ValueError(f"Filename '{filename}' not found in meta.yaml index.")

    # ID: 73a12ea2-7924-482f-a6c7-b0c67c56b486
    def load(self, logical_path: str) -> Dict[str, Any]:
        file_path = self.get_path(logical_path)
        try:
            return self._load_file_content(file_path)
        except FileNotFoundError:
            raise
        except (IOError, ValueError) as e:
            raise IOError(f"Failed to load or parse file for '{logical_path}': {e}")


try:
    settings = Settings()
except (RuntimeError, FileNotFoundError) as e:
    log.critical(f"FATAL ERROR during settings initialization: {e}")


# ID: a40df97d-3f3f-4ab9-9fca-7986ca5d5b25
def get_path_or_none(logical_path: str) -> Optional[Path]:
    try:
        if "settings" not in globals() or settings is None:
            return None
        return settings.get_path(logical_path)
    except Exception:
        return None
