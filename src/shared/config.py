# src/shared/config.py
"""
Centralizes configuration management using Pydantic to load and validate settings from environment variables and .env files.
"""

from __future__ import annotations

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
    KEY_STORAGE_DIR: Path = Path(".intent/keys")

    # --- System & Logging ---
    CORE_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORE_ACTION_LOG_PATH: Path = Path("logs/action_log.jsonl")
    LLM_ENABLED: bool = True
    CORE_DEV_FASTPATH: bool = False

    # --- Dev-specific variables ---
    CORE_DEV_KEY_PATH: Optional[str] = None
    CORE_DEV_APPROVER_EMAIL: Optional[str] = None

    # ======================================================================
    #                LLM RESOURCE REGISTRY CONFIGURATION
    # ======================================================================

    # -- Resource: deepseek_chat --
    DEEPSEEK_CHAT_API_URL: Optional[str] = None
    DEEPSEEK_CHAT_API_KEY: Optional[str] = None
    DEEPSEEK_CHAT_MODEL_NAME: Optional[str] = None

    # -- Resource: deepseek_coder --
    DEEPSEEK_CODER_API_URL: Optional[str] = None
    DEEPSEEK_CODER_API_KEY: Optional[str] = None
    DEEPSEEK_CODER_MODEL_NAME: Optional[str] = None

    # --- THIS IS THE FIX ---
    # Add the new Anthropic variables so Pydantic knows about them.
    # -- Resource: anthropic_claude_sonnet --
    ANTHROPIC_CLAUDE_SONNET_API_URL: Optional[str] = None
    ANTHROPIC_CLAUDE_SONNET_API_KEY: Optional[str] = None
    ANTHROPIC_CLAUDE_SONNET_MODEL_NAME: Optional[str] = None
    # --- END OF FIX ---

    class Config:
        """Defines Pydantic's behavior for the Settings model."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow other variables in the env, just don't load them.


# Create a single, reusable instance of the settings for other modules to import.
settings = Settings()
