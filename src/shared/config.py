# src/shared/config.py

"""
Bootstrap configuration.
Single Source of Truth for system paths and foundational connection strings.
This module is the base of the dependency tree; it contains no logic, only configuration.
"""

from __future__ import annotations

import json
import os  # ADDED
import sys  # ADDED
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


# ID: e2f3a5b1-7c4d-4f8a-9d2e-1b6c8a3e4f9d
def resolve_default_repo_path() -> Path:
    """Discover the repo root by walking up from cwd looking for ``.intent/``.

    Falls back to ``REPO_ROOT`` (the source-tree-relative path computed
    above) when no ``.intent/`` is found anywhere up the cwd chain. This
    makes the audit gate work against the consumer's repository when
    ``core-runtime`` is pip-installed: the consumer ``cd`` s into their
    repo and the audit auto-discovers ``.intent/`` without any env
    var configuration. Source-tree usage is unaffected — ``REPO_ROOT``
    contains ``.intent/`` and is the first matching candidate. See #544
    for the F-10.3 incident this resolves; #545 promoted the helper to
    a public API so the engine-side intent loaders can share it.
    """
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".intent").is_dir():
            return candidate
    return REPO_ROOT


# ID: 3a7b9c2d-1e4f-5a8b-c9d0-2e3f4a5b6c7d
def resolve_default_mind_path() -> Path:
    """Resolve the ``.intent/`` root for this invocation.

    Priority:
    1. First ``.intent/`` found walking up from cwd (consumer repo, post-onboard).
    2. Source-tree REPO_ROOT / ``.intent/`` (CORE dev environment).
    3. Bundled machinery floor at ``shared/_machinery_floor/`` (wheel install
       before ``project onboard`` has run — allows ``core-admin`` to start and
       deliver the floor without a chicken-and-egg crash).
    """
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        intent = candidate / ".intent"
        if intent.is_dir():
            return intent
    # Source-tree: REPO_ROOT should have .intent/
    source_intent = REPO_ROOT / ".intent"
    if source_intent.is_dir():
        return source_intent
    # Wheel install without a consumer .intent/ yet: use the bundled floor.
    # This is a read-only, schema-only root — rules/ and mappings/ are absent,
    # so governance evaluation is inert until the consumer runs `project onboard`.
    try:
        import importlib.resources

        floor = Path(
            str(importlib.resources.files("shared").joinpath("_machinery_floor"))
        )
        if floor.is_dir():
            return floor
    except Exception:
        pass
    return source_intent  # fall through — will surface a clear error at validation


# ID: 8d63432d-6c04-4696-b9e0-33d1174ebdf8
class Settings(BaseSettings):
    """
    Bootstrap configuration using Pydantic Settings.
    SSOT for paths and foundational connection strings.
    """

    # --- Operational State ---
    DEBUG: bool = False
    VERBOSE: bool = False

    # NEW: The "Teeth" Toggle (Phase 3 Hardening)
    # If False (default): Violations are reported but don't block execution.
    # If True: Any 'error' level violation halts the transaction immediately.
    CORE_STRICT_MODE: bool = Field(False, validation_alias="CORE_STRICT_MODE")

    CORE_ENV: str = Field("development", validation_alias="CORE_ENV")

    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", extra="allow", case_sensitive=True
    )

    _path_resolver: PathResolver | None = PrivateAttr(default=None)

    # --- Canonical Roots ---
    # Resolved via resolve_default_repo_path() so pip-installed
    # consumers auto-discover their repo from cwd. See #544.
    REPO_PATH: Path = Field(default_factory=resolve_default_repo_path)
    MIND: Path = Field(default_factory=resolve_default_mind_path)
    SPECS: Path = Field(default_factory=lambda: resolve_default_repo_path() / ".specs")
    BODY: Path = Field(default_factory=lambda: resolve_default_repo_path() / "src")

    # --- Standard Infrastructure Paths ---
    KEY_STORAGE_DIR: Path = Field(
        default_factory=lambda: resolve_default_repo_path() / ".intent" / "keys"
    )
    CORE_ACTION_LOG_PATH: Path = Field(
        default_factory=lambda: (
            __import__("shared.path_resolver", fromlist=["PathResolver"])
            .PathResolver.from_repo(REPO_ROOT)
            .logs_dir
            / "actions.jsonl"
        )
    )

    # --- Infrastructure Attributes ---
    # DATABASE_URL and QDRANT_URL default to None so that import-time
    # `Settings()` instantiation succeeds even when these env vars are
    # absent — the F-10.3 audit-gate runtime ships a pip-installed
    # core-runtime that must reach the `--offline` audit path without
    # any DB or Qdrant configuration. Consumers that actually need
    # these values (DB session manager, Qdrant client, etc.) still
    # fail loudly at the point of consumption rather than at import
    # time. See #544 for the full incident.
    DATABASE_URL: str | None = Field(None, validation_alias="DATABASE_URL")
    QDRANT_URL: str | None = Field(None, validation_alias="QDRANT_URL")

    LLM_API_URL: str = Field("", validation_alias="LLM_API_URL")
    LLM_API_KEY: str | None = Field(None, validation_alias="LLM_API_KEY")
    LLM_MODEL_NAME: str = Field("gpt-4o", validation_alias="LLM_MODEL_NAME")

    CORE_MASTER_KEY: str | None = Field(None, validation_alias="CORE_MASTER_KEY")
    LOG_LEVEL: str = Field("INFO", validation_alias="LOG_LEVEL")

    # UAC — auth token secrets and email delivery (ADR-124)
    JWT_SECRET_KEY: str = Field(
        "change-me-in-production", validation_alias="JWT_SECRET_KEY"
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        15, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        30, validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )
    # Must be explicitly set True in dev/test to permit the default JWT secret.
    # Affirmative opt-in so a misconfigured staging env cannot accidentally bypass
    # the startup guard via an env-name string match (#711).
    ALLOW_INSECURE_DEV_SECRET: bool = Field(
        False, validation_alias="ALLOW_INSECURE_DEV_SECRET"
    )
    RESEND_API_KEY: str | None = Field(None, validation_alias="RESEND_API_KEY")
    APP_BASE_URL: str = Field("http://localhost:8000", validation_alias="APP_BASE_URL")
    MAIL_FROM: str = Field(
        "CORE <noreply@core-governance.com>", validation_alias="MAIL_FROM"
    )
    # T6b: allowed CORS origins. Defaults to the Vite dev server; override in
    # production via CORS_ORIGINS='["https://app.example.com"]' (JSON array).
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias="CORS_ORIGINS",
    )

    LLM_ENABLED: bool = True
    QDRANT_COLLECTION_NAME: str = "core-code"
    LOCAL_EMBEDDING_DIM: int = 768
    LOCAL_EMBEDDING_MODEL_NAME: str = "nomic-embed-text"
    EMBED_MODEL_REVISION: str = "2025-09-15"
    CORE_MAX_CONCURRENT_REQUESTS: int = 2

    # Database connection pool sizing. SQLAlchemy defaults (pool_size=5,
    # max_overflow=10 → 15 max) are too low for the daemon's worker fleet
    # (21+ workers all hitting the DB at cold start), producing
    # QueuePool TimeoutError races. PG max_connections=100; these
    # defaults give 40 max per loop while leaving room for CLI tools and
    # ad-hoc queries. Override via env if running with more workers.
    DATABASE_POOL_SIZE: int = Field(20, validation_alias="DATABASE_POOL_SIZE")
    DATABASE_POOL_MAX_OVERFLOW: int = Field(
        20, validation_alias="DATABASE_POOL_MAX_OVERFLOW"
    )

    def __init__(self, **values: Any) -> None:
        is_testing = (
            "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None
        )

        if is_testing:
            os.environ["CORE_ENV"] = "TEST"

        # Skip .env under pytest: load_dotenv(override=True) would otherwise
        # overwrite the CORE_ENV=TEST signal set above and route the
        # environment-specific load below back to .env (the dev file),
        # leaving the suite pointed at the production DB. See #592.
        if not is_testing:
            load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

        super().__init__(**values)

        env_file_name = self._get_env_file_name(self.CORE_ENV)
        env_path = REPO_ROOT / env_file_name

        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
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
        self.SPECS = repo_path / ".specs"
        self.BODY = repo_path / "src"
        self._path_resolver = None

    # =========================================================================
    # TRANSITIONAL: load()
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
    # TRANSITIONAL ACCESSOR: get_path()
    # =========================================================================

    # ID: 4d351281-e7c8-424f-a916-a9626579580c
    def get_path(self, logical_path: str) -> Path:
        """
        TRANSITIONAL SHIM.
        Redirects logical path requests to the new PathResolver.
        """
        return self.paths.policy(logical_path)


settings = Settings()
