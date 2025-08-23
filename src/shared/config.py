# src/shared/config.py
"""
Centralized Pydantic-based settings management for CORE.

This module defines a `Settings` class that automatically loads configuration
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

    # --- Orchestrator LLM Configuration ---
    ORCHESTRATOR_API_URL: Optional[str] = None
    ORCHESTRATOR_API_KEY: Optional[str] = None
    ORCHESTRATOR_MODEL_NAME: str = "deepseek-chat"

    # --- Generator LLM Configuration ---
    GENERATOR_API_URL: Optional[str] = None
    GENERATOR_API_KEY: Optional[str] = None
    GENERATOR_MODEL_NAME: str = "deepseek-coder"

    # --- CLI & Governance Configuration ---
    KEY_STORAGE_DIR: Path = Path.home() / ".config" / "core"
    CORE_ACTION_LOG_PATH: Path = Path(".intent/change_log.json")

    # We must declare all variables from runtime_requirements.yaml so Pydantic
    # knows they are allowed.
    CORE_ENV: str = "production"
    CORE_DEV_FASTPATH: bool = False
    
    # --- THIS IS THE FIX ---
    LOG_LEVEL: str = "INFO"

    # These are optional, so we declare them as such.
    CORE_DEV_KEY_PATH: Optional[str] = None
    CORE_DEV_APPROVER_EMAIL: Optional[str] = None

    # --- Feature Flags ---
    LLM_ENABLED: bool = True

    class Config:
        """Defines Pydantic's behavior for the Settings model."""

        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single, reusable instance of the settings for other modules to import.
settings = Settings()