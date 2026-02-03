# src/shared/infrastructure/config_service.py
# ID: 47832f5d-142a-4637-923a-f0f3d76d6b08

"""
Configuration service that reads from the database as the single source of truth.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
ConfigService is infrastructure because it provides mechanical coordination
for configuration access without making strategic decisions about what
configuration values mean or how they should be used.

RESPONSIBILITIES:
- Retrieve configuration values from database
- Cache non-secret configuration for performance
- Coordinate secret retrieval from secrets service
- Provide read/write access to runtime settings

AUTHORITY LIMITS:
- Cannot interpret the semantic meaning of configuration values
- Cannot decide which configurations are "correct" or "important"
- Cannot choose between alternative configuration strategies
- Cannot make business logic decisions based on configuration

EXEMPTIONS:
- May access database directly (infrastructure coordination)
- May cache data in-memory (performance optimization)
- Exempt from Mind/Body/Will layer restrictions (infrastructure role)
- Subject to infrastructure authority boundary rules

Constitutional Principle: Mind/Body/Will Separation
- Mind (.intent/) defines WHAT should be configured
- Database stores the CURRENT state
- This service provides the Body/Will with READ/WRITE access under governance

Design choices:
- ✅ DB-as-SSOT (no runtime .env fallback)
- ✅ Async DI via AsyncSession (testable, no globals)
- ✅ Non-secret values cached in-memory for performance
- ✅ Secrets delegated to a dedicated secrets service (encryption/audit live there)

HEALED (V2.6.2):
- Added detach() method to release database sessions explicitly.

See: .intent/papers/CORE-Infrastructure-Definition.md Section 5
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.secrets_service import get_secrets_service
from shared.logger import getLogger


logger = getLogger(__name__)
__all__ = [
    "ConfigService",
    "LLMResourceConfig",
    "bootstrap_config_from_env",
    "config_service",
    "get_config_service",
]


# ID: 47832f5d-142a-4637-923a-f0f3d76d6b08
class ConfigService:
    """
    Provides configuration from database with caching.

    Usage:
        config = await ConfigService.create(db)
        model_name = await config.get("deepseek_chat.model_name")
        api_key = await config.get_secret("anthropic.api_key")
    """

    def __init__(self, db: AsyncSession | None, cache: dict[str, Any]):
        self.db = db
        self._cache = cache
        self._secrets_service: Any | None = None

    @classmethod
    # ID: 1d9345fd-5087-4b52-8c05-d4b6ab458c62
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
        logger.info("Loaded %s configuration values from database", len(cache))
        return cls(db, cache)

    # ID: 8876c24d-5e6f-4a8b-9c0d-1e2f3a4b5c6d
    def detach(self) -> None:
        """
        Releases the database session reference.
        Crucial for preventing SAWarning during process shutdown.
        """
        self.db = None
        self._secrets_service = None

    # ID: 59a5c363-943b-42aa-a048-b4c34a0e19cb
    async def get(
        self, key: str, default: str | None = None, required: bool = False
    ) -> str | None:
        """
        Get a non-secret configuration value.
        """
        value = self._cache.get(key)
        if value is None:
            if required:
                raise KeyError(f"Required config key '{key}' not found in database")
            return default
        return value

    # ID: afbb956b-f399-4630-8be7-afdb20d68f00
    async def get_secret(self, key: str, audit_context: str | None = None) -> str:
        """
        Get a secret configuration value (decrypted).
        """
        if self.db is None:
            raise RuntimeError(
                "ConfigService error: Database session has been detached."
            )

        if not self._secrets_service:
            self._secrets_service = await get_secrets_service(self.db)
        return await self._secrets_service.get_secret(
            self.db, key, audit_context=audit_context
        )

    # ID: f4493c4d-4248-4f21-8b16-a440b9433606
    async def get_int(self, key: str, default: int | None = None) -> int | None:
        """Get config value as integer."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return int(value) if value is not None else None

    # ID: aa36f26e-1381-4eb7-8870-da9cee67b054
    async def get_float(self, key: str, default: float | None = None) -> float | None:
        """Get config value as float."""
        value = await self.get(
            key, default=str(default) if default is not None else None
        )
        return float(value) if value is not None else None

    # ID: be84f22d-7a51-491c-965a-ef5d4306a895
    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get config value as boolean."""
        value = await self.get(key, default=str(default))
        if value is None:
            return default
        return str(value).lower() in ("true", "1", "yes", "on")

    # ID: 30b588cd-40f9-4684-a235-ffd139c90bfa
    async def set(self, key: str, value: str, description: str | None = None) -> None:
        """
        Set a non-secret configuration value.
        """
        if self.db is None:
            raise RuntimeError(
                "ConfigService error: Database session has been detached."
            )

        stmt = text(
            "\n            INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)\n            VALUES (:key, :value, :description, false, NOW())\n            ON CONFLICT (key)\n            DO UPDATE SET\n                value = EXCLUDED.value,\n                description = COALESCE(EXCLUDED.description, core.runtime_settings.description),\n                last_updated = NOW()\n            "
        )
        await self.db.execute(
            stmt, {"key": key, "value": value, "description": description}
        )
        await self.db.commit()
        self._cache[key] = value
        logger.info("Config '{key}' set to '%s'", value)

    # ID: c14f55cb-7f20-41ad-acfb-6830b6ed5387
    async def reload(self) -> None:
        """Reload non-secret config cache from database."""
        if self.db is None:
            raise RuntimeError(
                "ConfigService error: Database session has been detached."
            )

        stmt = text(
            "\n            SELECT key, value\n            FROM core.runtime_settings\n            WHERE is_secret = false\n            "
        )
        result = await self.db.execute(stmt)
        self._cache = {row[0]: row[1] for row in result.fetchall()}
        logger.info("Reloaded %s configuration values", len(self._cache))


# ID: 41e15669-c97e-405d-8a2b-1467cd650616
async def bootstrap_config_from_env() -> None:
    """
    Bootstrap database configuration from .env file.
    """
    from dotenv import dotenv_values

    from shared.infrastructure.database.session_manager import get_session

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
            if env_vars.get(env_key):
                await config.set(
                    db_key,
                    env_vars[env_key],
                    description=f"Bootstrapped from {env_key}",
                )
                migrated += 1
        logger.info("Bootstrapped %s config values from .env to database", migrated)


# ID: f39ed211-86d5-490b-aa4e-389de41b083f
class LLMResourceConfig:
    """
    Convenience wrapper for LLM resource configuration.
    """

    def __init__(self, config: ConfigService, resource_name: str):
        self.config = config
        self.resource_name = resource_name
        self._prefix = resource_name.lower().replace("-", "_")

    @classmethod
    # ID: 3e2e5335-d8ee-4a51-b307-db67fc502831
    async def for_resource(cls, config: ConfigService, resource_name: str):
        """Create config wrapper for a specific LLM resource."""
        return cls(config, resource_name)

    # ID: 4e31e5fa-9abc-4e1a-9086-98170e554b29
    async def get_api_key(self, audit_context: str | None = None) -> str:
        """Get API key for this resource."""
        key = f"{self._prefix}.api_key"
        return await self.config.get_secret(key, audit_context=audit_context)

    # ID: 895e21ac-ae06-4135-8606-16ae5653b44c
    async def get_model_name(self) -> str:
        """Get model name for this resource."""
        key = f"{self._prefix}.model_name"
        return await self.config.get(key, required=True)

    # ID: ba0e873c-7f09-4942-b569-5ebe5b43b4e0
    async def get_api_url(self) -> str:
        """Get API URL for this resource."""
        key = f"{self._prefix}.api_url"
        return await self.config.get(key, required=True)

    # ID: 1c758408-b430-40c4-bbe5-cdaa37695067
    async def get_max_concurrent(self) -> int:
        """Get max concurrent requests for this resource."""
        key = f"{self._prefix}.max_concurrent"
        default_key = "llm.default_max_concurrent"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2")
        return int(value)

    # ID: e3d22f99-4b0f-4715-be5b-752e0df97356
    async def get_rate_limit(self) -> float:
        """Get rate limit (seconds between requests) for this resource."""
        key = f"{self._prefix}.rate_limit"
        default_key = "llm.default_rate_limit"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2.0")
        return float(value)

    # ID: aaeb75b1-3017-44f8-818f-80575ed1461b
    async def get_timeout(self) -> int:
        """Get request timeout for this resource."""
        key = f"{self._prefix}.timeout"
        default_key = "llm.default_timeout"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="300")
        return int(value)


# ID: 9d684627-5b6e-49c0-be02-cbab851e6067
async def config_service(db: AsyncSession) -> ConfigService:
    """Back-compat: some modules do `from shared.infrastructure.config_service import config_service`."""
    return await ConfigService.create(db)


get_config_service = config_service
