# src/shared/config.py

"""
Bootstrap configuration.
Single Source of Truth for system paths and foundational connection strings.
This module is the base of the dependency tree; it contains no logic, only configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from dotenv import load_dotenv
from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.path_resolver import PathResolver

logger = getLogger(__name__)

# Calculation: src/shared/config.py -> shared -> src -> root
REPO_ROOT = Path(__file__).resolve().parents[2]


# ID: 8d63432d-6c04-4696-b9e0-33d1174ebdf8
class Settings(BaseSettings):
    """
    Bootstrap configuration using Pydantic Settings.
    SSOT for paths and foundational connection strings.
    """

    # --- Operational State (Required by CLI callbacks and Fix commands) ---
    DEBUG: bool = False
    VERBOSE: bool = False

    # Pydantic will automatically populate this from the environment variable 'CORE_ENV'
    CORE_ENV: str = Field("development", validation_alias="CORE_ENV")

    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", extra="allow", case_sensitive=True
    )

    # Internal cache for the PathResolver instance
    _path_resolver: PathResolver | None = PrivateAttr(default=None)

    # --- Canonical Roots ---
    REPO_PATH: Path = REPO_ROOT
    MIND: Path = REPO_ROOT / ".intent"
    BODY: Path = REPO_ROOT / "src"

    # --- Standard Infrastructure Paths ---
    KEY_STORAGE_DIR: Path = REPO_ROOT / ".intent" / "keys"
    CORE_ACTION_LOG_PATH: Path = REPO_ROOT / "logs" / "actions.jsonl"

    # --- Infrastructure Attributes ---
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")
    QDRANT_URL: str = Field(..., validation_alias="QDRANT_URL")

    # Required by llm_gate.py and others
    LLM_API_URL: str = Field("", validation_alias="LLM_API_URL")
    LLM_API_KEY: str | None = Field(None, validation_alias="LLM_API_KEY")
    LLM_MODEL_NAME: str = Field("gpt-4o", validation_alias="LLM_MODEL_NAME")

    CORE_MASTER_KEY: str | None = Field(None, validation_alias="CORE_MASTER_KEY")
    LOG_LEVEL: str = Field("INFO", validation_alias="LOG_LEVEL")

    LLM_ENABLED: bool = True
    QDRANT_COLLECTION_NAME: str = "core_symbols"
    LOCAL_EMBEDDING_DIM: int = 768
    LOCAL_EMBEDDING_MODEL_NAME: str = "nomic-embed-text"
    EMBED_MODEL_REVISION: str = "2025-09-15"
    CORE_MAX_CONCURRENT_REQUESTS: int = 2
    LLM_REQUEST_TIMEOUT: int = 300

    def __init__(self, **values: Any) -> None:
        # 1. Load root .env
        load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

        # 2. Pydantic handles CORE_ENV population here
        super().__init__(**values)

        # 3. Load environment-specific file if it exists
        env_file_name = self._get_env_file_name(self.CORE_ENV)
        env_path = REPO_ROOT / env_file_name
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            # Re-run init to pick up specific vars
            super().__init__(**values)

    def _get_env_file_name(self, core_env: str) -> str:
        mapping = {
            "TEST": ".env.test",
            "PROD": ".env.prod",
            "PRODUCTION": ".env.prod",
            "DEV": ".env",
            "DEVELOPMENT": ".env",
        }
        return mapping.get(core_env.upper(), ".env")

    # ID: 9191b227-04d8-4f61-8e48-26fbdeb4c107
    def initialize_for_test(self, repo_path: Path) -> None:
        """Re-roots settings for test environments."""
        self.REPO_PATH = repo_path
        self.MIND = repo_path / ".intent"
        self.BODY = repo_path / "src"
        self._path_resolver = None

    # =========================================================================
    # TRANSITIONAL SHIM: load()
    # =========================================================================

    # ID: 174906ec-e521-4e15-b464-d2b082486dc2
    def load(self, logical_path: str) -> dict[str, Any]:
        """
        Resolves a constitutional artifact via PathResolver and parses it.
        This satisfies the 150+ call sites still calling settings.load().
        """
        try:
            target_path = self.paths.policy(logical_path)

            if not target_path.exists():
                return {}

            content = target_path.read_text(encoding="utf-8")
            if target_path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(content)
                return cast(dict[str, Any], data) if isinstance(data, dict) else {}

            if target_path.suffix == ".json":
                return cast(dict[str, Any], json.loads(content))

            return {}
        except Exception as e:
            logger.debug("Shim load failed for %s: %s", logical_path, e)
            return {}

    # =========================================================================
    # PATH RESOLVER (The Map)
    # =========================================================================

    @property
    # ID: f2412e87-c192-4b3d-ba0e-e514ecff2f38
    def paths(self) -> PathResolver:
        """Unified interface for all file system paths in CORE."""
        if self._path_resolver is None:
            from shared.path_resolver import PathResolver

            self._path_resolver = PathResolver.from_repo(
                repo_root=self.REPO_PATH,
                intent_root=self.MIND,
            )
        return self._path_resolver

    # =========================================================================
    # LEGACY ACCESSOR SHIM: get_path()
    # =========================================================================

    # ID: 4d351281-e7c8-424f-a916-a9626579580c
    def get_path(self, logical_path: str) -> Path:
        """
        TRANSITIONAL SHIM.
        Redirects logical path requests to the new PathResolver.
        """
        return self.paths.policy(logical_path)


settings = Settings()
