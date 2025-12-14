# src/shared/infrastructure/context/cache.py

"""ContextCache - Hash-based packet caching and replay.

Caches packets by task spec hash to avoid rebuilding identical contexts.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .serializers import ContextSerializer


logger = logging.getLogger(__name__)


# ID: 52c404cf-d08b-4899-85e0-549e898f1c7a
class ContextCache:
    """Manages packet caching and retrieval."""

    def __init__(self, cache_dir: str = "work/context_cache"):
        """Initialize cache with storage directory.

        Args:
            cache_dir: Directory for cached packets
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = 24

    # ID: b7fa4d4a-de80-46c4-8a07-154ab9ff0145
    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve cached packet by key.

        Args:
            cache_key: Cache key (task spec hash)

        Returns:
            Cached packet or None if not found/expired
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"
        if not cache_file.exists():
            logger.debug("Cache miss: %s", cache_key[:8])
            return None
        age_hours = self._get_age_hours(cache_file)
        if age_hours > self.ttl_hours:
            logger.debug("Cache expired: %s (%sh old)", cache_key[:8], age_hours)
            cache_file.unlink()
            return None
        try:
            packet = ContextSerializer.from_yaml(str(cache_file))
            logger.debug("Cache hit: %s", cache_key[:8])
            return packet
        except Exception as e:
            logger.error("Failed to load cache: %s", e)
            return None

    # ID: 29357f38-eb35-4168-94e4-e69f8ffc39ef
    def put(self, cache_key: str, packet: dict[str, Any]) -> None:
        """Store packet in cache.

        Args:
            cache_key: Cache key (task spec hash)
            packet: ContextPackage dict
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"
        try:
            ContextSerializer.to_yaml(packet, str(cache_file))
            logger.debug("Cached packet: %s", cache_key[:8])
        except Exception as e:
            logger.error("Failed to cache packet: %s", e)

    # ID: 66c9dc8e-2345-45db-9dfd-384e8800ab99
    def invalidate(self, cache_key: str) -> None:
        """Remove cached packet.

        Args:
            cache_key: Cache key to invalidate
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"
        if cache_file.exists():
            cache_file.unlink()
            logger.debug("Invalidated cache: %s", cache_key[:8])

    # ID: 8b3b0288-46c7-4637-9a40-eda87269d16e
    def clear_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        for cache_file in self.cache_dir.glob("*.yaml"):
            age_hours = self._get_age_hours(cache_file)
            if age_hours > self.ttl_hours:
                cache_file.unlink()
                removed += 1
                logger.debug("Removed expired cache: %s", cache_file.stem)
        if removed > 0:
            logger.info("Cleared %s expired cache entries", removed)
        return removed

    # ID: e1fee6fd-42a6-4a3c-b44f-4fe7d0ad21fd
    def clear_all(self) -> int:
        """Remove all cached packets.

        Returns:
            Number of entries removed
        """
        removed = 0
        for cache_file in self.cache_dir.glob("*.yaml"):
            cache_file.unlink()
            removed += 1
        logger.info("Cleared all %s cache entries", removed)
        return removed

    def _get_age_hours(self, file_path: Path) -> float:
        """Get file age in hours.

        Args:
            file_path: Path to file

        Returns:
            Age in hours
        """
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
        now = datetime.now(UTC)
        age = now - mtime
        return age.total_seconds() / 3600
