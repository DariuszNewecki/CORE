# src/shared/config.py
"""
Intent: Centralize configuration with safe defaults and backward-compatible
env mapping. Accept both *_MODEL_NAME and *_MODEL, plus provide the fields
tests expect (LLM_ENABLED, ORCHESTRATOR_API_URL, etc.).
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load from .env if present; ignore unknown keys (forward-compatible).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Paths (your repo’s schema) -----------------------------------------
    MIND: str = Field(default=".intent", description="Path to intent files")
    BODY: str = Field(default="src", description="Path to code body")
    REPO_PATH: str = Field(default=".", description="Repo root")
    CORE_ACTION_LOG_PATH: str = Field(
        default="logs/action_log.jsonl", description="Append-only action log path"
    )

    # --- Logging / Flags -----------------------------------------------------
    CORE_LOG_JSON: bool = Field(default=False, description="JSON logs when true")
    CORE_LOG_LEVEL: str = Field(default="INFO", description="Root log level")
    LLM_ENABLED: bool = Field(
        default=False,
        description="Disable external LLM calls by default in tests/CI",
    )

    # --- Orchestrator (accept both NAME and non-NAME) ------------------------
    # Canonical attribute we use internally:
    ORCHESTRATOR_MODEL: str = Field(
        default="deepseek-chat",
        description="Primary model for orchestration",
        validation_alias="ORCHESTRATOR_MODEL_NAME",  # also read *_MODEL_NAME
    )
    ORCHESTRATOR_API_URL: str = Field(
        default="",
        description="HTTP endpoint for OrchestratorClient (can stay empty in tests)",
    )
    ORCHESTRATOR_API_KEY: str = Field(default="", description="API key if needed")

    # --- Generator (accept both NAME and non-NAME) ---------------------------
    GENERATOR_MODEL: str = Field(
        default="deepseek-coder",
        description="Model for code generation",
        validation_alias="GENERATOR_MODEL_NAME",  # also read *_MODEL_NAME
    )
    GENERATOR_API_URL: str = Field(
        default="",
        description="HTTP endpoint for GeneratorClient (can stay empty in tests)",
    )
    GENERATOR_API_KEY: str = Field(default="", description="API key if needed")

    # Back-compat property names so existing code/tests can use either form ----
    @property
    def ORCHESTRATOR_MODEL_NAME(self) -> str:  # noqa: N802
        return self.ORCHESTRATOR_MODEL

    @property
    def GENERATOR_MODEL_NAME(self) -> str:  # noqa: N802
        return self.GENERATOR_MODEL

    # Helpful snake_case conveniences (optional)
    @property
    def orchestrator_model(self) -> str:
        return self.ORCHESTRATOR_MODEL

    @property
    def generator_model(self) -> str:
        return self.GENERATOR_MODEL

    # Normalize empty URLs if you want a local default for dev; leave as-is for CI.
    @model_validator(mode="after")
    def _fill_reasonable_local_defaults(self) -> "Settings":
        def _maybe_fill(url: str) -> str:
            return url or ""  # keep empty by default; tests monkeypatch HTTP anyway

        object.__setattr__(
            self, "ORCHESTRATOR_API_URL", _maybe_fill(self.ORCHESTRATOR_API_URL)
        )
        object.__setattr__(
            self, "GENERATOR_API_URL", _maybe_fill(self.GENERATOR_API_URL)
        )
        return self


# Singleton instance
settings = Settings()
