# src/services/config_service.py
"""
Provides a centralized service for accessing runtime configuration.

This service is the single source of truth for configuration for the running
application. It prioritizes values from the database and falls back to the
environment (.env file) if a value is not found in the database.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

from services.database.session_manager import get_session

log = getLogger("config_service")


# ID: 266a4a72-e1e5-4c7a-911f-ede92726c323
class ConfigurationService:
    """A service that provides configuration from the DB with a .env fallback."""

    _cache: Dict[str, Any] = {}
    _initialized: bool = False
    _lock = asyncio.Lock()

    async def _load_settings_from_db(self):
        """Loads all non-secret settings from the database into the cache."""
        async with self._lock:
            if self._initialized:
                return

            log.info(
                "Initializing ConfigurationService: loading settings from database..."
            )
            try:
                async with get_session() as session:
                    stmt = text(
                        "SELECT key, value FROM core.runtime_settings WHERE is_secret = FALSE"
                    )
                    result = await session.execute(stmt)
                    for row in result:
                        self._cache[row.key] = row.value
                self._initialized = True
                log.info(
                    f"Loaded {len(self._cache)} configuration settings from the database."
                )
            except Exception as e:
                log.error(
                    f"Failed to load configuration from database: {e}. Will rely on .env fallback."
                )
                # Mark as initialized to prevent retries on every call
                self._initialized = True

    # ID: 4c588ad7-2835-475c-8b69-0d122aebedcb
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a configuration value.

        It checks the database-backed cache first, then falls back to the
        environment-loaded settings object, and finally returns the default.
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


# Create a single, global instance for easy access
config_service = ConfigurationService()


# ID: e9bf3e46-3eba-4e6d-88bc-40eda491a2bd
def get_config_service() -> ConfigurationService:
    """Factory function to get the global instance of the ConfigurationService."""
    return config_service
