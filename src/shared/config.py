# src/shared/config.py
"""
Centralizes configuration management using Pydantic to load and validate settings from environment variables and .env files.
Add new LLM resources via .env (e.g., DEEPSEEK_CHAT_API_URL) and propose updates to resource_manifest.yaml (see docs/03_GOVERNANCE.md).
Version: 1.0.0
Last Updated: 2025-08-26
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import ConfigDict, ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Loads and validates system settings for CORE, ensuring safe configuration.
    Supports paths, logging, and LLM resources for cognitive_roles.yaml and resource_manifest.yaml.
    """

    # --- Metadata ---
    VERSION: str = "1.0.0"
    LAST_UPDATED: str = "2025-08-26T22:00:00Z"

    # --- Path Configuration ---
    MIND: Path = Path(".intent")
    BODY: Path = Path("src")
    REPO_PATH: Path = Path(".")
    KEY_STORAGE_DIR: Path = Path(".intent/keys")
    RESOURCE_MANIFEST_PATH: Path = Path(".intent/knowledge/resource_manifest.yaml")
    COGNITIVE_ROLES_PATH: Path = Path(".intent/knowledge/cognitive_roles.yaml")

    # --- System & Logging ---
    CORE_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORE_ACTION_LOG_PATH: Path = Path("logs/action_log.jsonl")
    LLM_ENABLED: bool = True
    CORE_DEV_FASTPATH: bool = False

    # --- Dev-specific variables ---
    CORE_DEV_KEY_PATH: Optional[str] = None
    CORE_DEV_APPROVER_EMAIL: Optional[str] = None

    # --- LLM Resource Registry Configuration ---
    # Made these optional to allow tests to run without a .env file
    DEEPSEEK_CHAT_API_URL: Optional[str] = None
    DEEPSEEK_CHAT_API_KEY: Optional[str] = None
    DEEPSEEK_CHAT_MODEL_NAME: str = "chat-v1"
    DEEPSEEK_CHAT_MAX_TOKENS: int = 2048
    DEEPSEEK_CHAT_MAX_REQUESTS: int = 20

    DEEPSEEK_CODER_API_URL: Optional[str] = None
    DEEPSEEK_CODER_API_KEY: Optional[str] = None
    DEEPSEEK_CODER_MODEL_NAME: str = "coder-v2"
    DEEPSEEK_CODER_MAX_TOKENS: int = 2048
    DEEPSEEK_CODER_MAX_REQUESTS: int = 50

    ANTHROPIC_CLAUDE_SONNET_API_URL: Optional[str] = None
    ANTHROPIC_CLAUDE_SONNET_API_KEY: Optional[str] = None
    ANTHROPIC_CLAUDE_SONNET_MODEL_NAME: str = "sonnet-3.5"
    ANTHROPIC_CLAUDE_SONNET_MAX_TOKENS: int = 8192
    ANTHROPIC_CLAUDE_SONNET_MAX_REQUESTS: int = 10

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(f"Configuration validation failed: {e}")
