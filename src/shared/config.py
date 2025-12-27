# src/shared/config.py

"""Provides functionality for the config module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from dotenv import load_dotenv
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.path_resolver import PathResolver


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
    _path_resolver: PathResolver | None = PrivateAttr(default=None)

    REPO_PATH: Path = REPO_ROOT
    MIND: Path = REPO_PATH / ".intent"
    BODY: Path = REPO_PATH / "src"

    KEY_STORAGE_DIR: Path = REPO_PATH / ".intent" / "keys"

    # NOTE: left as-is for now; we will align these to var/ later as part of consolidation
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
        # Invalidate path resolver cache when repo path changes
        self._path_resolver = None

    def _load_meta_config(self):
        meta_path = self.REPO_PATH / ".intent" / "meta.yaml"
        if not meta_path.exists():
            self._meta_config = {}
            return
        try:
            self._meta_config = self._load_file_content(meta_path)
        except (OSError, ValueError) as e:
            raise RuntimeError(f"FATAL: Could not parse .intent/meta.yaml: {e}") from e

    def _load_file_content(self, file_path: Path) -> dict[str, Any]:
        content = file_path.read_text("utf-8")
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        if file_path.suffix == ".json":
            return json.loads(content) or {}
        raise ValueError(f"Unsupported config file type: {file_path}")

    # =========================================================================
    # NEW: PathResolver Interface
    # =========================================================================

    @property
    # ID: b9f3cdd1-bb43-4159-9b5f-8e1b3fa0ed2e
    def paths(self) -> PathResolver:
        """
        Unified interface for all file system paths in CORE.

        IMPORTANT:
        - PathResolver is PURE (no mkdir). All directory creation belongs to FileHandler.
        """
        if self._path_resolver is None:
            from shared.path_resolver import PathResolver

            # New constructor: repo_root + intent_root (no meta)
            # intent_root is fixed at repo/.intent and provided for IntentRepository use.
            self._path_resolver = PathResolver.from_repo(
                repo_root=self.REPO_PATH,
                intent_root=self.MIND,
            )

            # Validate structure on first access (pure check; does not create)
            issues = self._path_resolver.validate_structure()
            # New implementation returns dict; older variants returned list[str]
            if isinstance(issues, dict):
                missing = issues.get("missing_dirs") or []
                if missing:
                    logger.warning(
                        "Path structure validation found missing dirs: %s",
                        "; ".join(missing),
                    )
            elif isinstance(issues, list) and issues:
                logger.warning(
                    "Path structure validation found issues: %s", "; ".join(issues)
                )

        return self._path_resolver

    # =========================================================================
    # LEGACY: Keep existing methods for backward compatibility
    # =========================================================================

    # ID: c5d53841-226f-403c-891e-20d723f8b28e
    def get_path(self, logical_path: str) -> Path:
        """
        LEGACY: Get path from meta.yaml logical path.

        NOTE: Prefer using settings.paths.* for new code.
        This method is kept for backward compatibility.
        """
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
        except (KeyError, TypeError) as e:
            raise FileNotFoundError(
                f"Logical path '{logical_path}' not found or invalid in meta.yaml index."
            ) from e

    # ID: defdb6ae-211b-4ca7-abda-3582519cc6e3
    def find_logical_path_for_file(self, filename: str) -> str:
        """LEGACY: Find logical path for a filename in meta.yaml."""

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


settings = Settings()
