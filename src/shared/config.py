# src/shared/config.py
"""
Configuration loading and validation for the CORE system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


# CAPABILITY: config.settings.load
class Settings(BaseSettings):
    """
    Validated configuration for the CORE system, loaded from environment variables.
    It uses `extra='allow'` to dynamically load any additional environment
    variables, which can be accessed via `model_extra`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
    )

    # --- Core, explicitly typed attributes that the system relies on ---
    MIND: Path = Path(".intent")
    BODY: Path = Path("src")
    REPO_PATH: Path = Path(".")
    LLM_ENABLED: bool = True
    CORE_MAX_CONCURRENT_REQUESTS: int = 5
    LOG_LEVEL: str = "INFO"
    CORE_ACTION_LOG_PATH: Path = Path("logs/action_log.jsonl")
    RESOURCE_MANIFEST_PATH: Path = Path(".intent/knowledge/resource_manifest.yaml")

    @property
    # CAPABILITY: config.environment.extra_fields
    def model_extra(self) -> Dict[str, Any]:
        """
        Return extra fields that were loaded from environment variables.
        This provides backward compatibility for accessing dynamic variables.
        """
        return getattr(self, "__pydantic_extra__", {})


try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(f"Configuration validation failed: {e}")
