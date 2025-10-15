# src/services/config_service.py
"""
Provides a centralized service for accessing runtime configuration.

This service is the single source of truth for configuration for the running application.
It prioritizes values from the database and falls back to the environment (.env file)
if a value is not found in the database.

ENHANCED: Now supports encrypted secrets via SecretsService.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from cryptography.fernet import Fernet
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.session_manager import get_session

log = getLogger("config_service")


# ID: secrets-manager-001
# ID: b3687136-ebc4-40d0-85a9-20ca0a67f4ac
class SecretsManager:
    """
    Handles encryption/decryption of secrets.

    This is a lightweight version integrated into ConfigService.
    """

    def __init__(self):
        self._cipher: Fernet | None = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-load the cipher when first needed."""
        if self._initialized:
            return

        master_key = os.getenv("CORE_MASTER_KEY")
        if not master_key:
            log.warning(
                "CORE_MASTER_KEY not found in environment. "
                "Encrypted secrets will not be available."
            )
            self._cipher = None
        else:
            try:
                self._cipher = Fernet(master_key.encode())
                log.info("SecretsManager initialized with master key")
            except Exception as e:
                log.error(f"Failed to initialize secrets cipher: {e}")
                self._cipher = None

        self._initialized = True

    # ID: 7761508a-e278-4a25-84dd-662a6dc0da64
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a secret value."""
        self._ensure_initialized()

        if not self._cipher:
            raise RuntimeError(
                "SecretsManager not initialized. Set CORE_MASTER_KEY in .env"
            )

        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    # ID: 747d32a4-1a21-4a8e-9f23-879fe3ddad76
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret value."""
        self._ensure_initialized()

        if not self._cipher:
            raise RuntimeError(
                "SecretsManager not initialized. Set CORE_MASTER_KEY in .env"
            )

        return self._cipher.encrypt(plaintext.encode()).decode()


# ID: 266a4a72-e1e5-4c7a-911f-ede92726c323
class ConfigService:
    """
    A service that provides configuration from the DB with a .env fallback.

    ENHANCED FEATURES:
    - Supports encrypted secrets via get_secret()
    - Cache invalidation via reload()
    - Audit logging for secret access
    - Better error handling
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        self._secrets_manager = SecretsManager()

    async def _load_settings_from_db(self):
        """Loads all non-secret settings from the database into the cache."""
        async with self._lock:
            if self._initialized:
                return

            log.info("Initializing ConfigService: loading settings from database...")
            try:
                async with get_session() as session:
                    stmt = text(
                        "SELECT key, value FROM core.runtime_settings WHERE is_secret = FALSE"
                    )
                    result = await session.execute(stmt)
                    self._cache.clear()  # Clear cache before reload
                    for row in result:
                        self._cache[row.key] = row.value

                self._initialized = True
                log.info(
                    f"Loaded {len(self._cache)} configuration settings from the database."
                )
            except Exception as e:
                log.error(
                    f"Failed to load configuration from database: {e}. "
                    f"Will rely on .env fallback."
                )
                # DON'T mark as initialized on failure - allow retry
                # But wait a bit before next attempt to avoid spam
                await asyncio.sleep(5)

    # ID: 4c588ad7-2835-475c-8b69-0d122aebedcb
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a configuration value.

        It checks the database-backed cache first, then falls back to the
        environment-loaded settings object, and finally returns the default.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        if not self._initialized:
            await self._load_settings_from_db()

        # 1. Try to get from the database cache
        value = self._cache.get(key)
        if value is not None:
            return value

        # 2. Fallback: try to get from the .env-backed settings object
        value = getattr(settings, key, None)
        if value is not None:
            return value

        # 3. Return the default
        return default

    # ID: 37a77ebc-3d57-4982-ab06-0b3bd33f0085
    async def get_int(self, key: str, default: int | None = None) -> int | None:
        """Get configuration value as integer."""
        value = await self.get(key, default=default)
        if value is None:
            return None
        return int(value)

    # ID: 4ee6c6a8-9feb-488e-b0fc-756dde0e18d6
    async def get_float(self, key: str, default: float | None = None) -> float | None:
        """Get configuration value as float."""
        value = await self.get(key, default=default)
        if value is None:
            return None
        return float(value)

    # ID: 4bef5aa4-8a2c-4d96-b713-44649a582576
    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean."""
        value = await self.get(key, default=default)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")

    # ID: config-service-secrets-001
    # ID: b3718640-1d8e-4889-9575-c051dca5b942
    async def get_secret(
        self,
        key: str,
        audit_context: str | None = None,
    ) -> str:
        """
        Get an encrypted secret from the database.

        Args:
            key: Secret key (e.g., "anthropic.api_key")
            audit_context: Context for audit log (e.g., "planner_agent")

        Returns:
            Decrypted secret value

        Raises:
            KeyError: If secret not found
            RuntimeError: If CORE_MASTER_KEY not set

        Example:
            api_key = await config_service.get_secret("anthropic.api_key", "planner")
        """
        try:
            async with get_session() as session:
                stmt = text(
                    "SELECT value FROM core.runtime_settings "
                    "WHERE key = :key AND is_secret = TRUE"
                )
                result = await session.execute(stmt, {"key": key})
                row = result.fetchone()

                if not row:
                    raise KeyError(f"Secret '{key}' not found in database")

                # Decrypt the value
                decrypted_value = self._secrets_manager.decrypt(row.value)

                # Audit the access
                await self._audit_secret_access(session, key, audit_context)

                return decrypted_value

        except KeyError:
            raise
        except Exception as e:
            log.error(f"Failed to retrieve secret '{key}': {e}")
            raise

    # ID: 8562280a-0934-4271-9e86-bc17f51200b9
    async def set_secret(
        self,
        key: str,
        value: str,
        description: str | None = None,
    ) -> None:
        """
        Store an encrypted secret in the database.

        Args:
            key: Secret key
            value: Plaintext secret value (will be encrypted)
            description: Optional description
        """
        encrypted_value = self._secrets_manager.encrypt(value)

        async with get_session() as session:
            stmt = text(
                """
                INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)
                VALUES (:key, :value, :description, TRUE, NOW())
                ON CONFLICT (key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    description = EXCLUDED.description,
                    last_updated = NOW()
            """
            )

            await session.execute(
                stmt,
                {
                    "key": key,
                    "value": encrypted_value,
                    "description": description or f"Encrypted secret: {key}",
                },
            )
            await session.commit()

        log.info(f"Secret '{key}' stored successfully (encrypted)")

    async def _audit_secret_access(
        self,
        session: AsyncSession,
        key: str,
        context: str | None,
    ) -> None:
        """Log secret access for audit trail."""
        try:
            stmt = text(
                """
                INSERT INTO core.agent_memory (
                    cognitive_role,
                    memory_type,
                    content,
                    relevance_score,
                    created_at
                ) VALUES (
                    :role,
                    'fact',
                    :content,
                    1.0,
                    NOW()
                )
            """
            )

            await session.execute(
                stmt,
                {
                    "role": context or "system",
                    "content": f"Accessed secret: {key}",
                },
            )
            # Let the caller handle commit
        except Exception as e:
            # Don't fail secret retrieval if audit fails
            log.error(f"Failed to audit secret access: {e}")

    # ID: 384585a4-b0ec-4d18-ac66-c032a978e15b
    async def reload(self) -> None:
        """
        Force reload of configuration from database.

        Use this if config changes in DB and you need to pick up changes
        without restarting the application.
        """
        async with self._lock:
            log.info("Reloading configuration from database...")
            self._initialized = False
            await self._load_settings_from_db()

    # ID: c96a9014-16f5-4be1-a368-fe5b711e2f59
    async def set(
        self,
        key: str,
        value: str,
        description: str | None = None,
    ) -> None:
        """
        Set a non-secret configuration value in the database.

        Note: This bypasses constitutional governance. Use with caution!
        For production changes, use the governance workflow.
        """
        async with get_session() as session:
            stmt = text(
                """
                INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)
                VALUES (:key, :value, :description, FALSE, NOW())
                ON CONFLICT (key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    description = COALESCE(EXCLUDED.description, core.runtime_settings.description),
                    last_updated = NOW()
            """
            )

            await session.execute(
                stmt,
                {"key": key, "value": value, "description": description},
            )
            await session.commit()

        # Update cache
        self._cache[key] = value
        log.info(f"Config '{key}' set to '{value}'")


# Create a single, global instance for easy access
config_service = ConfigService()


# ID: e9bf3e46-3eba-4e6d-88bc-40eda491a2bd
def get_config_service() -> ConfigService:
    """Factory function to get the global instance of the ConfigService."""
    return config_service


# ID: config-service-llm-helper-001
# ID: 3131b840-be2c-49f5-962e-8e2bfe5346ce
class LLMResourceConfig:
    """
    Convenience helper for accessing LLM resource configuration.

    Usage:
        llm_config = LLMResourceConfig(config_service, "anthropic")
        api_key = await llm_config.get_api_key()
        model = await llm_config.get_model_name()
        max_concurrent = await llm_config.get_max_concurrent()
    """

    def __init__(self, config_service: ConfigService, resource_name: str):
        self.config = config_service
        self.resource_name = resource_name
        # Normalize: anthropic_claude_sonnet -> anthropic
        self._prefix = resource_name.lower().replace("-", "_").split("_")[0]

    # ID: c0653290-9582-422a-8a98-f5945dac8e4d
    async def get_api_key(self, audit_context: str | None = None) -> str:
        """Get API key for this resource (decrypted)."""
        key = f"{self._prefix}.api_key"
        return await self.config.get_secret(key, audit_context=audit_context)

    # ID: 497b9a82-d9f2-4b67-aa92-088f5522d66e
    async def get_model_name(self) -> str:
        """Get model name for this resource."""
        # Try specific key first, fall back to resource_name key
        key = f"{self._prefix}.model_name"
        value = await self.config.get(key)
        if not value:
            # Fallback: try with full resource name
            key = f"{self.resource_name}.model_name"
            value = await self.config.get(key)
        return value or "unknown"

    # ID: d4ada9de-74a6-49d2-8bdb-588fb2b12d7d
    async def get_max_concurrent(self) -> int:
        """Get max concurrent requests for this resource."""
        key = f"{self._prefix}.max_concurrent"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get("llm.default_max_concurrent", default="2")
        return int(value)

    # ID: ac47f3f9-f8fe-4969-b25e-f982e0e43e98
    async def get_rate_limit(self) -> float:
        """Get rate limit (seconds between requests)."""
        key = f"{self._prefix}.rate_limit"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get("llm.default_rate_limit", default="2.0")
        return float(value)

    # ID: 85821815-8bf2-460f-929c-2975e69be8ce
    async def get_timeout(self) -> int:
        """Get request timeout in seconds."""
        key = f"{self._prefix}.timeout"
        value = await self.config.get(key)
        if not value:
            value = await self.config.get("llm.default_timeout", default="300")
        return int(value)
