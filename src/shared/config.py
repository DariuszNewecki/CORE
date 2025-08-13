# src/shared/config.py
"""
Centralized Pydantic-based settings management for CORE.

This module defines a `Settings` class that automatically loads configuration
from environment variables and .env files. It provides a single, typed source
of truth for all configuration parameters.
"""
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    A Pydantic settings model that loads configuration from the environment.
    It provides a typed, validated access to all system settings.
    """
    # --- Path Configuration ---
    # These have sensible defaults but can be overridden by the .env file.
    MIND: Path = Path(".intent")
    BODY: Path = Path("src")
    REPO_PATH: Path = Path(".")

    # --- Orchestrator LLM Configuration ---
    # May be empty when LLMs are disabled.
    ORCHESTRATOR_API_URL: str | None = None
    ORCHESTRATOR_API_KEY: str | None = None
    ORCHESTRATOR_MODEL_NAME: str = "deepseek-chat"

    # --- Generator LLM Configuration ---
    # May be empty when LLMs are disabled.
    GENERATOR_API_URL: str | None = None
    GENERATOR_API_KEY: str | None = None
    GENERATOR_MODEL_NAME: str = "deepseek-coder"
    
    # --- CLI & Governance Configuration ---
    KEY_STORAGE_DIR: Path = Path.home() / ".config" / "core"
    CORE_ACTION_LOG_PATH: Path

    # --- Feature Flags ---
    # Disables LLM client initialization at startup when false.
    LLM_ENABLED: bool = True

    class Config:
        """Defines Pydantic's behavior for the Settings model."""
        # This tells Pydantic to load variables from a .env file if it exists.
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Create a single, reusable instance of the settings for other modules to import.
settings = Settings()