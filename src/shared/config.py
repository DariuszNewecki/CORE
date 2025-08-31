# src/shared/config.py
"""
Configuration loading and validation for the CORE system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Validated configuration for the CORE system, loaded from environment variables.
    It uses `extra='allow'` to dynamically load any additional environment
    variables, which can be accessed via `model_extra`.
    """

    # This configuration is now more robust and explicit, incorporating your suggestions.
    # It tells Pydantic to handle loading the .env file itself, solving the race condition.
    model_config = SettingsConfigDict(
        env_file=".env",  # Looks for a .env file in the project root.
        env_file_encoding="utf-8",
        extra="allow",  # Allows loading variables not explicitly defined in this class.
        case_sensitive=True,  # Enforces that environment variable names are case-sensitive.
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

    # The custom @model_validator has been removed in favor of Pydantic's robust handling.

    @property
    def model_extra(self) -> Dict[str, Any]:
        """
        Return extra fields that were loaded from environment variables.
        This provides backward compatibility for accessing dynamic variables.
        """
        # In Pydantic v2, extra fields are stored in __pydantic_extra__
        return getattr(self, "__pydantic_extra__", {})


try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(f"Configuration validation failed: {e}")
