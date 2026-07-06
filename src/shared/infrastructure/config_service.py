# src/shared/infrastructure/config_service.py

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

HEALED (V2.3.0):
- Added detach() method to release database sessions explicitly.

See: .specs/papers/CORE-Infrastructure-Definition.md Section 5
"""

from __future__ import annotations

from typing import Any, Literal, overload

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.secrets_service import get_secrets_service
from shared.logger import getLogger


logger = getLogger(__name__)
__all__ = [
    "ConfigService",
    "LLMResourceConfig",
    "config_service",
    "get_config_service",
]


# ID: 84230e10-80e5-448b-931c-602e7d84f5d8
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

        ADR-052 Phase 4: migration complete — always loads from typed tables.
        The runtime_settings fallback path is retired; the table is dropped.
        """
        cache = await cls._load_from_typed_tables(db)
        logger.info(
            "Loaded %s configuration values from typed tables (ADR-052)",
            len(cache),
        )
        return cls(db, cache)

    @staticmethod
    async def _load_from_typed_tables(db: AsyncSession) -> dict[str, Any]:
        """Build the legacy flat-key cache from ADR-052 typed tables.

        Expands every active ``llm_resources`` row into the
        ``<lower(env_prefix)>.{model_name,api_url,max_concurrent,rate_limit}``
        keys that ``LLMResourceConfig`` expects. The ``system_config``
        singleton is expanded into the three ``llm_enabled`` aliases
        and the timeout / embed-revision keys. Result is a plain
        ``dict[str, Any]`` matching what the runtime_settings query
        used to produce.
        """
        cache: dict[str, Any] = {}

        resources_q = text(
            "SELECT env_prefix, model_name, api_url, "
            "max_concurrent, rate_limit_seconds "
            "FROM core.llm_resources WHERE is_available = true"
        )
        resources = await db.execute(resources_q)
        for row in resources.mappings():
            prefix = (row["env_prefix"] or "").lower()
            if not prefix:
                continue
            if row["model_name"] is not None:
                cache[f"{prefix}.model_name"] = row["model_name"]
            if row["api_url"] is not None:
                cache[f"{prefix}.api_url"] = row["api_url"]
            cache[f"{prefix}.max_concurrent"] = str(row["max_concurrent"])
            cache[f"{prefix}.rate_limit"] = str(row["rate_limit_seconds"])

        system_q = text(
            "SELECT llm_enabled, request_timeout_seconds, embed_model_revision "
            "FROM core.system_config LIMIT 1"
        )
        sysrow = (await db.execute(system_q)).mappings().fetchone()
        if sysrow is not None:
            enabled_text = "true" if sysrow["llm_enabled"] else "false"
            cache["system.llm_enabled"] = enabled_text
            cache["llm.enabled"] = enabled_text
            cache["LLM_ENABLED"] = enabled_text
            timeout = str(sysrow["request_timeout_seconds"])
            cache["llm.default_timeout"] = timeout
            cache["llm_request.timeout"] = timeout
            if sysrow["embed_model_revision"]:
                cache["embed_model.revision"] = sysrow["embed_model_revision"]

        return cache

    # ID: a9b6ddbb-5ac8-40f9-adaa-afd582d911b4
    def detach(self) -> None:
        """
        Releases the database session reference.
        Crucial for preventing SAWarning during process shutdown.
        """
        self.db = None
        self._secrets_service = None

    @overload
    # ID: 4960b91c-128b-4aaa-b652-083349902fc2
    async def get(
        self, key: str, default: str | None = ..., *, required: Literal[True]
    ) -> str: ...

    @overload
    # ID: a981a162-33d8-46e8-8782-253ce1b502f0
    async def get(
        self, key: str, default: str | None = ..., required: bool = ...
    ) -> str | None: ...

    # ID: ad1081e4-2c8d-41c3-afd9-6eb675dfa5de
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
    async def get_secret(
        self,
        key: str,
        audit_context: str | None = None,
        *,
        resource_name: str | None = None,
    ) -> str:
        """
        Get a secret configuration value (decrypted).

        Forwards `audit_context` (cognitive_role) and `resource_name`
        (free-text resource identifier) to SecretsService — see #434.
        """
        if self.db is None:
            raise RuntimeError(
                "ConfigService error: Database session has been detached."
            )

        if not self._secrets_service:
            self._secrets_service = await get_secrets_service(self.db)
        return await self._secrets_service.get_secret(
            self.db, key, audit_context=audit_context, resource_name=resource_name
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

    # ID: c14f55cb-7f20-41ad-acfb-6830b6ed5387
    async def reload(self) -> None:
        """Reload non-secret config cache from typed tables (ADR-052 Phase 4)."""
        if self.db is None:
            raise RuntimeError(
                "ConfigService error: Database session has been detached."
            )
        self._cache = await self._load_from_typed_tables(self.db)
        logger.info(
            "Reloaded %s configuration values from typed tables", len(self._cache)
        )


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
        """Get API key for this resource.

        Always forwards `resource_name` (FK-free column) from the
        wrapper's own identity, in addition to the caller's optional
        `audit_context` (FK to cognitive_roles.role). The audit row
        carries both columns when supplied — see #434.
        """
        key = f"{self._prefix}.api_key"
        return await self.config.get_secret(
            key,
            audit_context=audit_context,
            resource_name=self.resource_name,
        )

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
        return int(value or "2")

    # ID: e3d22f99-4b0f-4715-be5b-752e0df97356
    async def get_rate_limit(self) -> float:
        """Get rate limit (seconds between requests) for this resource."""
        key = f"{self._prefix}.rate_limit"
        default_key = "llm.default_rate_limit"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="2.0")
        return float(value or "2.0")

    # ID: aaeb75b1-3017-44f8-818f-80575ed1461b
    async def get_timeout(self) -> int:
        """Get request timeout for this resource."""
        key = f"{self._prefix}.timeout"
        default_key = "llm.default_timeout"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get(default_key, default="300")
        return int(value or "300")


# ID: 9d684627-5b6e-49c0-be02-cbab851e6067
async def config_service(db: AsyncSession) -> ConfigService:
    """Back-compat: some modules do `from shared.infrastructure.config_service import config_service`."""
    return await ConfigService.create(db)


get_config_service = config_service
