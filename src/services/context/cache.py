# src/services/context/cache.py

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


# ID: 07952d27-3794-4c53-bd9d-9ff95c068951
class ContextCache:
    """Manages packet caching and retrieval."""

    def __init__(self, cache_dir: str = "work/context_cache"):
        """Initialize cache with storage directory.

        Args:
            cache_dir: Directory for cached packets
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = 24  # Cache lifetime

    # ID: 9702a3a3-9cf5-41ec-9e85-7bf41be1af57
    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve cached packet by key.

        Args:
            cache_key: Cache key (task spec hash)

        Returns:
            Cached packet or None if not found/expired
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"

        if not cache_file.exists():
            logger.debug(f"Cache miss: {cache_key[:8]}")
            return None

        # Check expiration
        age_hours = self._get_age_hours(cache_file)
        if age_hours > self.ttl_hours:
            logger.debug(f"Cache expired: {cache_key[:8]} ({age_hours:.1f}h old)")
            cache_file.unlink()
            return None

        # Load cached packet
        try:
            packet = ContextSerializer.from_yaml(str(cache_file))
            # Downgraded to DEBUG
            logger.debug(f"Cache hit: {cache_key[:8]}")
            return packet
        except Exception as e:
            logger.error("Failed to load cache: %s", e)
            return None

    # ID: 37ec4f3d-e3a9-4a48-bd9f-396d81674875
    def put(self, cache_key: str, packet: dict[str, Any]) -> None:
        """Store packet in cache.

        Args:
            cache_key: Cache key (task spec hash)
            packet: ContextPackage dict
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"

        try:
            ContextSerializer.to_yaml(packet, str(cache_file))
            # Downgraded to DEBUG
            logger.debug(f"Cached packet: {cache_key[:8]}")
        except Exception as e:
            logger.error("Failed to cache packet: %s", e)

    # ID: 246e0f98-8d6f-4e14-9642-8b05ff6fc80d
    def invalidate(self, cache_key: str) -> None:
        """Remove cached packet.

        Args:
            cache_key: Cache key to invalidate
        """
        cache_file = self.cache_dir / f"{cache_key}.yaml"

        if cache_file.exists():
            cache_file.unlink()
            logger.debug(f"Invalidated cache: {cache_key[:8]}")

    # ID: 780655c4-539c-4ed7-94b4-3bfaec639a7e
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
                logger.debug(f"Removed expired cache: {cache_file.stem}")

        if removed > 0:
            logger.info("Cleared %s expired cache entries", removed)

        return removed

    # ID: 0d0e49c2-c5b8-4623-9bb1-855cda775bb3
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
