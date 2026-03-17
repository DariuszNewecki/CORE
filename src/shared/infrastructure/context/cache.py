# src/shared/infrastructure/context/cache.py

"""ContextCache - hash-based ContextPacket caching."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger

from .serializers import ContextSerializer


logger = getLogger(__name__)


# ID: 53829663-9f4a-40ff-b425-837b872e5c45
class ContextCache:
    """Manages packet caching and retrieval."""

    def __init__(self, cache_dir: str = "work/context_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = 24

    # ID: c2612fcd-1454-4d75-9061-ad89275709ae
    def get(self, cache_key: str) -> dict[str, Any] | None:
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

    # ID: 7943de7d-89dc-423b-9cf5-4dfe0e6592a4
    def set(self, cache_key: str, packet: dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{cache_key}.yaml"
        try:
            ContextSerializer.to_yaml(packet, str(cache_file))
            logger.debug("Cached packet: %s", cache_key[:8])
        except Exception as e:
            logger.error("Failed to cache packet: %s", e)

    # ID: 90fa3e32-096c-431e-8c5f-e49df45ce2c7
    def put(self, cache_key: str, packet: dict[str, Any]) -> None:
        """Backward-compatible alias."""
        self.set(cache_key, packet)

    # ID: be37327c-36a7-41a6-b456-545b4db732ce
    def invalidate(self, cache_key: str) -> None:
        cache_file = self.cache_dir / f"{cache_key}.yaml"
        if cache_file.exists():
            cache_file.unlink()
            logger.debug("Invalidated cache: %s", cache_key[:8])

    # ID: 1c41c3f4-a188-4544-af77-12dc0c593f74
    def clear_expired(self) -> int:
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

    # ID: f5553609-0d49-41fd-aec4-eb3175b0b08e
    def clear_all(self) -> int:
        removed = 0
        for cache_file in self.cache_dir.glob("*.yaml"):
            cache_file.unlink()
            removed += 1

        logger.info("Cleared all %s cache entries", removed)
        return removed

    def _get_age_hours(self, file_path: Path) -> float:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
        now = datetime.now(UTC)
        age = now - mtime
        return age.total_seconds() / 3600
