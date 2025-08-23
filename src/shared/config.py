# src/shared/config.py
"""
Centralized Pydantic-based settings management for CORE.

This module defines a Settings class that automatically loads configuration
from environment variables and .env files. It provides a single, typed source
of truth for all configuration parameters.
"""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    A Pydantic settings model that loads configuration from the environment.
    It provides a typed, validated access to all system settings.
    """

    # --- Path Configuration ---
    MIND: Path = Path(".intent")
    BODY: Path = Path("src")
    REPO_PATH: Path = Path(".")

    # --- System & Logging ---
    CORE_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORE_ACTION_LOG_PATH: Path = Path("logs/action_log.jsonl")
    LLM_ENABLED: bool = True
    CORE_DEV_FASTPATH: bool = False

    # ======================================================================
    #                LLM RESOURCE REGISTRY CONFIGURATION
    # ======================================================================
    # These variables are loaded from the .env file and correspond to the
    # `env_prefix` in .intent/knowledge/resource_manifest.yaml.

    # -- Resource: deepseek_chat --
    DEEPSEEK_CHAT_API_URL: Optional[str] = None
    DEEPSEEK_CHAT_API_KEY: Optional[str] = None
    DEEPSEEK_CHAT_MODEL_NAME: Optional[str] = None

    # -- Resource: deepseek_coder --
    DEEPSEEK_CODER_API_URL: Optional[str] = None
    DEEPSEEK_CODER_API_KEY: Optional[str] = None
    DEEPSEEK_CODER_MODEL_NAME: Optional[str] = None

    class Config:
        """Defines Pydantic's behavior for the Settings model."""

        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single, reusable instance of the settings for other modules to import.
settings = Settings()