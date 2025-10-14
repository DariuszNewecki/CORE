# src/services/config_service.py
"""
Configuration service that reads from database as single source of truth.

Constitutional Principle: Mind/Body/Will Separation
- Mind (.intent/) defines WHAT should be configured
- Database stores the CURRENT state
- This service provides Body (code) access to configuration

Migration Path:
1. Bootstrap: .env → DB (one-time)
2. Runtime: Code reads from DB only
3. Updates: Changes go through constitutional governance
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.secrets_service import get_secrets_service
from shared.logger import getLogger

log = getLogger(__name__)


# ID: config-service-001
class ConfigService:
    """
    Provides configuration from database with caching.

    Usage:
        config = await ConfigService.create(db)
        model_name = await config.get("deepseek_chat.model_name")
        api_key = await config.get_secret("anthropic.api_key")
    """

    def __init__(self, db: AsyncSession, cache: dict[str, Any]):
        self.db = db
        self._cache = cache
        self._secrets_service: Any | None = None

    @classmethod
    async def create(cls, db: AsyncSession) -> ConfigService:
        """
        Factory method to create ConfigService with preloaded cache.

        This loads all non-secret config into memory for performance.
        Secrets are fetched on-demand for security.
        """
        # Load all non-secret config
        query = text(
            """
            SELECT key, value
            FROM core.runtime_settings
            WHERE is_secret = false
        """
        )

        result = await db.execute(query)
        cache = {row[0]: row[1] for row in result.fetchall()}

        log.info(f"Loaded {len(cache)} configuration values from database")

        return cls(db, cache)

    async def get(
        self,
        key: str,
        default: str | None = None,
        required: bool = False,
    ) -> str | None:
        """
        Get a non-secret configuration value.

        Args:
            key: Config key (e.g., "deepseek_chat.model_name")
            default: Default value if not found
            required: If True, raise error if not found

        Returns:
            Config value or default

        Raises:
            KeyError: If required=True and key not found
        """
        value = self._cache.get(key)

        if value is None:
            if required:
                raise KeyError(f"Required config key '{key}' not found in database")
            return default

        return value

    async def get_secret(
        self,
        key: str,
        audit_context: str | None = None,
    ) -> str:
        """
        Get a secret configuration value (decrypted).

        Args:
            key: Secret key (e.g., "anthropic.api_key")
            audit_context: Context for audit log

        Returns:
            Decrypted secret value

        Raises:
            KeyError: If secret not found
        """
        if not self._secrets_service:
            self._secrets_service = await get_secrets_service(self.db)

        return await self._secrets_service.get_secret(
            self.db,
            key,
            audit_context=audit_context,
        )

    async def get_int(self, key: str, default: int | None = None) -> int | None:
        """Get config value as integer."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return int(value) if value else None

    async def get_float(self, key: str, default: float | None = None) -> float | None:
        """Get config value as float."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return float(value) if value else None

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get config value as boolean."""
        value = await self.get(key, default=str(default))
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    async def set(
        self,
        key: str,
        value: str,
        description: str | None = None,
    ) -> None:
        """
        Set a non-secret configuration value.

        Note: This should go through governance for production changes!
        """
        query = text(
            """
            INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)
            VALUES (:key, :value, :description, false, NOW())
            ON CONFLICT (key)
            DO UPDATE SET
                value = EXCLUDED.value,
                description = COALESCE(EXCLUDED.description, core.runtime_settings.description),
                last_updated = NOW()
        """
        )

        await self.db.execute(
            query,
            {"key": key, "value": value, "description": description},
        )
        await self.db.commit()

        # Update cache
        self._cache[key] = value

        log.info(f"Config '{key}' set to '{value}'")

    async def reload_cache(self) -> None:
        """Reload non-secret config cache from database."""
        query = text(
            """
            SELECT key, value
            FROM core.runtime_settings
            WHERE is_secret = false
        """
        )

        result = await self.db.execute(query)
        self._cache = {row[0]: row[1] for row in result.fetchall()}

        log.info(f"Reloaded {len(self._cache)} configuration values")


# ID: config-service-002
async def bootstrap_config_from_env() -> None:
    """
    Bootstrap database configuration from .env file.

    This should be run ONCE when setting up a new environment.
    After this, all config changes go through the database.

    Usage:
        poetry run core-admin manage config bootstrap
    """
    from dotenv import dotenv_values

    from services.database.session_manager import get_session

    env_vars = dotenv_values(".env")

    # Map env vars to database keys
    config_mapping = {
        # LLM Resources
        "OLLAMA_LOCAL_MODEL_NAME": "ollama_local.model_name",
        "OLLAMA_LOCAL_MAX_CONCURRENT_REQUESTS": "ollama_local.max_concurrent",
        "OLLAMA_LOCAL_SECONDS_BETWEEN_REQUESTS": "ollama_local.rate_limit",
        "DEEPSEEK_CHAT_MODEL_NAME": "deepseek_chat.model_name",
        "DEEPSEEK_CHAT_MAX_CONCURRENT_REQUESTS": "deepseek_chat.max_concurrent",
        "DEEPSEEK_CHAT_SECONDS_BETWEEN_REQUESTS": "deepseek_chat.rate_limit",
        "DEEPSEEK_CODER_MODEL_NAME": "deepseek_coder.model_name",
        "DEEPSEEK_CODER_MAX_CONCURRENT_REQUESTS": "deepseek_coder.max_concurrent",
        "DEEPSEEK_CODER_SECONDS_BETWEEN_REQUESTS": "deepseek_coder.rate_limit",
        "ANTHROPIC_CLAUDE_SONNET_MODEL_NAME": "anthropic.model_name",
        "ANTHROPIC_CLAUDE_SONNET_MAX_CONCURRENT_REQUESTS": "anthropic.max_concurrent",
        "ANTHROPIC_CLAUDE_SONNET_SECONDS_BETWEEN_REQUESTS": "anthropic.rate_limit",
        # Embedding
        "LOCAL_EMBEDDING_MODEL_NAME": "embedding.model_name",
        "LOCAL_EMBEDDING_DIM": "embedding.dimensions",
        "LOCAL_EMBEDDING_MAX_CONCURRENT_REQUESTS": "embedding.max_concurrent",
        # System
        "LLM_REQUEST_TIMEOUT": "llm.default_timeout",
        "CORE_MAX_CONCURRENT_REQUESTS": "llm.default_max_concurrent",
        "LLM_SECONDS_BETWEEN_REQUESTS": "llm.default_rate_limit",
        "LOG_LEVEL": "system.log_level",
        "LLM_ENABLED": "system.llm_enabled",
    }

    async with get_session() as db:
        config = await ConfigService.create(db)

        migrated = 0
        for env_key, db_key in config_mapping.items():
            if env_key in env_vars and env_vars[env_key]:
                await config.set(
                    db_key,
                    env_vars[env_key],
                    description=f"Bootstrapped from {env_key}",
                )
                migrated += 1

        log.info(f"Bootstrapped {migrated} config values from .env to database")


# ID: config-service-003
class LLMResourceConfig:
    """
    Convenience wrapper for LLM resource configuration.

    Usage:
        config = await ConfigService.create(db)
        anthropic = await LLMResourceConfig.for_resource(config, "anthropic")
        api_key = await anthropic.get_api_key()
        model = await anthropic.get_model_name()
    """

    def __init__(self, config: ConfigService, resource_name: str):
        self.config = config
        self.resource_name = resource_name
        self._prefix = resource_name.lower().replace("-", "_")

    @classmethod
    async def for_resource(cls, config: ConfigService, resource_name: str):
        """Create config wrapper for a specific LLM resource."""
        return cls(config, resource_name)

    async def get_api_key(self, audit_context: str | None = None) -> str:
        """Get API key for this resource."""
        key = f"{self._prefix}.api_key"
        return await self.config.get_secret(key, audit_context=audit_context)

    async def get_model_name(self) -> str:
        """Get model name for this resource."""
        key = f"{self._prefix}.model_name"
        return await self.config.get(key, required=True)

    async def get_api_url(self) -> str:
        """Get API URL for this resource."""
        key = f"{self._prefix}.api_url"
        return await self.config.get(key, required=True)

    async def get_max_concurrent(self) -> int:
        """Get max concurrent requests for this resource."""
        key = f"{self._prefix}.max_concurrent"
        default_key = "llm.default_max_concurrent"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2")
        return int(value)

    async def get_rate_limit(self) -> float:
        """Get rate limit (seconds between requests) for this resource."""
        key = f"{self._prefix}.rate_limit"
        default_key = "llm.default_rate_limit"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2.0")
        return float(value)

    async def get_timeout(self) -> int:
        """Get request timeout for this resource."""
        key = f"{self._prefix}.timeout"
        default_key = "llm.default_timeout"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="300")
        return int(value)
