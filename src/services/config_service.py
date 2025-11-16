# src/services/config_service.py

"""
Configuration service that reads from the database as the single source of truth.

Constitutional Principle: Mind/Body/Will Separation
- Mind (.intent/) defines WHAT should be configured
- Database stores the CURRENT state
- This service provides the Body/Will with READ/WRITE access under governance

Design choices:
- ✅ DB-as-SSOT (no runtime .env fallback)
- ✅ Async DI via AsyncSession (testable, no globals)
- ✅ Non-secret values cached in-memory for performance
- ✅ Secrets delegated to a dedicated secrets service (encryption/audit live there)
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.secrets_service import get_secrets_service

logger = getLogger(__name__)

__all__ = [
    "ConfigService",
    "bootstrap_config_from_env",
    "LLMResourceConfig",
    "config_service",
    "get_config_service",
]


# ID: 3daef5a1-6481-43a9-83c5-898a0c4116eb
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
    # ID: c329b5b3-cbbf-43da-b86b-bf191cb28932
    async def create(cls, db: AsyncSession) -> ConfigService:
        """
        Factory: create ConfigService with preloaded cache.
        Loads all non-secret config into memory for performance.
        Secrets are fetched on-demand for security.
        """
        query = text(
            "\n            SELECT key, value\n            FROM core.runtime_settings\n            WHERE is_secret = false\n            "
        )
        result = await db.execute(query)
        cache = {row[0]: row[1] for row in result.fetchall()}
        logger.info(f"Loaded {len(cache)} configuration values from database")
        return cls(db, cache)

    # ID: 65300fd0-ce8f-4d35-b048-f92c03ee1740
    async def get(
        self, key: str, default: str | None = None, required: bool = False
    ) -> str | None:
        """
        Get a non-secret configuration value.

        Args:
            key: Config key (e.g., "deepseek_chat.model_name")
            default: Default value if not found
            required: If True, raise error if not found
        """
        value = self._cache.get(key)
        if value is None:
            if required:
                raise KeyError(f"Required config key '{key}' not found in database")
            return default
        return value

    # ID: 179b046b-0ccd-4ea8-9f86-96d467076cde
    async def get_secret(self, key: str, audit_context: str | None = None) -> str:
        """
        Get a secret configuration value (decrypted).
        Secrets are stored encrypted in DB and audited in the secrets service.
        """
        if not self._secrets_service:
            self._secrets_service = await get_secrets_service(self.db)
        return await self._secrets_service.get_secret(
            self.db, key, audit_context=audit_context
        )

    # ID: 7e69104f-6462-41db-8696-6a5494b3a652
    async def get_int(self, key: str, default: int | None = None) -> int | None:
        """Get config value as integer."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return int(value) if value is not None else None

    # ID: 6b6f8932-6ef5-4cd9-8ce9-2562bccd39d6
    async def get_float(self, key: str, default: float | None = None) -> float | None:
        """Get config value as float."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return float(value) if value is not None else None

    # ID: 9a5bcc06-d006-493a-8463-cdcad0d43d02
    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get config value as boolean."""
        value = await self.get(key, default=str(default))
        if value is None:
            return default
        return str(value).lower() in ("true", "1", "yes", "on")

    # ID: a8012c92-7d29-485c-941c-117dfeb5b9c8
    async def set(self, key: str, value: str, description: str | None = None) -> None:
        """
        Set a non-secret configuration value.

        Note: Production changes should go through governance!
        """
        stmt = text(
            "\n            INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)\n            VALUES (:key, :value, :description, false, NOW())\n            ON CONFLICT (key)\n            DO UPDATE SET\n                value = EXCLUDED.value,\n                description = COALESCE(EXCLUDED.description, core.runtime_settings.description),\n                last_updated = NOW()\n            "
        )
        await self.db.execute(
            stmt, {"key": key, "value": value, "description": description}
        )
        await self.db.commit()
        self._cache[key] = value
        logger.info(f"Config '{key}' set to '{value}'")

    # ID: 831360f5-139d-444c-8fa6-f6833e30e86d
    async def reload(self) -> None:
        """Reload non-secret config cache from database."""
        stmt = text(
            "\n            SELECT key, value\n            FROM core.runtime_settings\n            WHERE is_secret = false\n            "
        )
        result = await self.db.execute(stmt)
        self._cache = {row[0]: row[1] for row in result.fetchall()}
        logger.info(f"Reloaded {len(self._cache)} configuration values")


# ID: 2c56e90f-a575-4ca3-a383-129eabd76ffa
async def bootstrap_config_from_env() -> None:
    """
    Bootstrap database configuration from .env file.

    Run ONCE when setting up a new environment.
    After this, all config changes go through the database.
    """
    from dotenv import dotenv_values

    from services.database.session_manager import get_session

    env_vars = dotenv_values(".env")
    config_mapping = {
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
        "LOCAL_EMBEDDING_MODEL_NAME": "embedding.model_name",
        "LOCAL_EMBEDDING_DIM": "embedding.dimensions",
        "LOCAL_EMBEDDING_MAX_CONCURRENT_REQUESTS": "embedding.max_concurrent",
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
        logger.info(f"Bootstrapped {migrated} config values from .env to database")


# ID: 3dfbf86d-dcd2-4f05-ad86-15277a6c24ac
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
    # ID: ef686803-3648-4341-a372-e7cb4cceeba7
    async def for_resource(cls, config: ConfigService, resource_name: str):
        """Create config wrapper for a specific LLM resource."""
        return cls(config, resource_name)

    # ID: 74563b88-9afd-4708-89e3-a1a54fe044f9
    async def get_api_key(self, audit_context: str | None = None) -> str:
        """Get API key for this resource."""
        key = f"{self._prefix}.api_key"
        return await self.config.get_secret(key, audit_context=audit_context)

    # ID: 60bc1805-92e5-480f-b131-54bef4ff8034
    async def get_model_name(self) -> str:
        """Get model name for this resource."""
        key = f"{self._prefix}.model_name"
        return await self.config.get(key, required=True)

    # ID: 258bbffd-f2be-43ec-b27c-62ed77d1b974
    async def get_api_url(self) -> str:
        """Get API URL for this resource."""
        key = f"{self._prefix}.api_url"
        return await self.config.get(key, required=True)

    # ID: 27765568-de8e-4df7-92d6-3753085db4f4
    async def get_max_concurrent(self) -> int:
        """Get max concurrent requests for this resource."""
        key = f"{self._prefix}.max_concurrent"
        default_key = "llm.default_max_concurrent"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2")
        return int(value)

    # ID: 5b9b0ba7-6cb2-4f3b-9b52-7d84d99fa7b9
    async def get_rate_limit(self) -> float:
        """Get rate limit (seconds between requests) for this resource."""
        key = f"{self._prefix}.rate_limit"
        default_key = "llm.default_rate_limit"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2.0")
        return float(value)

    # ID: c2b5af79-ad37-4b09-ae8e-ead9cdcb975a
    async def get_timeout(self) -> int:
        """Get request timeout for this resource."""
        key = f"{self._prefix}.timeout"
        default_key = "llm.default_timeout"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="300")
        return int(value)


# ID: bc0a7994-398e-43e6-b959-d2b3d064fdbd
async def config_service(db: AsyncSession) -> ConfigService:
    """Back-compat: some modules do `from services.config_service import config_service`."""
    return await ConfigService.create(db)


get_config_service = config_service
