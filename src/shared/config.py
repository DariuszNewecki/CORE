# src/shared/config.py

"""Provides functionality for the config module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger


logger = getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]


# ID: 8d63432d-6c04-4696-b9e0-33d1174ebdf8
class Settings(BaseSettings):
    """
    Bootstrap configuration ONLY. Loads the bare minimum required to connect
    to the database (the system's Mind) and provides "Pathfinder" methods
    to access constitutional files via the .intent/meta.yaml index.

    All other application settings are loaded from the database via the ConfigService.
    """

    CORE_ENV: str = "development"

    @property
    def _env_file(self) -> str:
        mapping = {
            "TEST": ".env.test",
            "PROD": ".env.prod",
            "PRODUCTION": ".env.prod",
            "DEV": ".env",
            "DEVELOPMENT": ".env",
        }
        return mapping.get(self.CORE_ENV.upper(), ".env")

    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", extra="allow", case_sensitive=True
    )
    _meta_config: dict[str, Any] = PrivateAttr(default_factory=dict)
    REPO_PATH: Path = REPO_ROOT
    MIND: Path = REPO_PATH / ".intent"
    BODY: Path = REPO_PATH / "src"
    KEY_STORAGE_DIR: Path = REPO_PATH / ".intent" / "keys"
    CORE_ACTION_LOG_PATH: Path = REPO_PATH / "logs" / "actions.jsonl"
    DATABASE_URL: str
    QDRANT_URL: str
    CORE_MASTER_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    LLM_ENABLED: bool = True
    QDRANT_COLLECTION_NAME: str = "core_symbols"
    LOCAL_EMBEDDING_DIM: int = 768
    LOCAL_EMBEDDING_MODEL_NAME: str = "nomic-embed-text"
    EMBED_MODEL_REVISION: str = "2025-09-15"
    CORE_MAX_CONCURRENT_REQUESTS: int = 2
    LLM_REQUEST_TIMEOUT: int = 300

    def __init__(self, **values: Any):
        load_dotenv(REPO_ROOT / ".env", override=True)
        core_env = values.get("CORE_ENV") or "development"
        env_file = REPO_ROOT / self._get_env_file_name(core_env)
        if env_file.exists():
            load_dotenv(env_file, override=True)
            logger.debug("Loaded environment file: %s", env_file)
        else:
            logger.warning("Environment file not found: %s, using defaults", env_file)
        super().__init__(**values)
        if (self.REPO_PATH / ".intent" / "meta.yaml").exists():
            self._load_meta_config()

    def _get_env_file_name(self, core_env: str) -> str:
        mapping = {
            "TEST": ".env.test",
            "PROD": ".env.prod",
            "PRODUCTION": ".env.prod",
            "DEV": ".env",
            "DEVELOPMENT": ".env",
        }
        return mapping.get(core_env.upper(), ".env")

    # ID: f3368871-0171-4724-992b-7144beda92f2
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
        except (OSError, ValueError) as e:
            raise RuntimeError(f"FATAL: Could not parse .intent/meta.yaml: {e}")

    def _load_file_content(self, file_path: Path) -> dict[str, Any]:
        content = file_path.read_text("utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        if file_path.suffix == ".json":
            return json.loads(content) or {}
        raise ValueError(f"Unsupported config file type: {file_path}")

    # ID: c5d53841-226f-403c-891e-20d723f8b28e
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

    # ID: defdb6ae-211b-4ca7-abda-3582519cc6e3
    def find_logical_path_for_file(self, filename: str) -> str:
        def _search(d: Any) -> str | None:
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

    # ID: ce3d8a38-9dd7-4467-a921-2576d9a3d3eb
    def load(self, logical_path: str) -> dict[str, Any]:
        file_path = self.get_path(logical_path)
        try:
            return self._load_file_content(file_path)
        except FileNotFoundError:
            raise
        except (OSError, ValueError) as e:
            raise OSError(f"Failed to load or parse file for '{logical_path}': {e}")


try:
    settings = Settings()
except (RuntimeError, FileNotFoundError) as e:
    logger.critical("FATAL ERROR during settings initialization: %s", e)
    raise


# ID: c920ea8e-ecae-48f4-8fd4-c1dda9a506e7
def get_path_or_none(logical_path: str) -> Path | None:
    try:
        if "settings" not in globals() or settings is None:
            return None
        return settings.get_path(logical_path)
    except Exception:
        return None
