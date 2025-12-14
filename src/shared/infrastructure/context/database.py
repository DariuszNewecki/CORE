# src/shared/infrastructure/context/database.py

"""ContextDatabase - Persistence layer for context packets.

Records packet metadata to context_packets table.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


# ID: b85ce303-a95a-4382-ba97-536af5e6e92e
class ContextDatabase:
    """Manages database persistence for context packets."""

    def __init__(self):
        """
        Initializes the database component. The session is expected to be
        set by the caller before a method is invoked.
        """
        self.db: AsyncSession | None = None

    # ID: f4e7d3b7-1465-48f9-aefd-acc6c43fda3b
    async def save_packet_metadata(
        self, packet: dict[str, Any], file_path: str, size_bytes: int
    ) -> bool:
        """Save packet metadata to database."""
        if not self.db:
            logger.warning("No database service - skipping metadata save")
            return False
        try:
            header = packet["header"]
            policy = packet.get("policy", {})
            provenance = packet.get("provenance", {})
            build_stats = provenance.get("build_stats", {})
            query = text(
                "\n                INSERT INTO core.context_packets (\n                    packet_id, task_id, task_type, created_at, privacy,\n                    remote_allowed, packet_hash, cache_key, tokens_est,\n                    size_bytes, build_ms, items_count, redactions_count,\n                    path, metadata, builder_version\n                ) VALUES (\n                    :packet_id, :task_id, :task_type, :created_at, :privacy,\n                    :remote_allowed, :packet_hash, :cache_key, :tokens_est,\n                    :size_bytes, :build_ms, :items_count, :redactions_count,\n                    :path, :metadata, :builder_version\n                )\n            "
            )
            metadata_payload = {
                "problem": packet.get("problem", {}),
                "scope": packet.get("scope", {}),
                "constraints": packet.get("constraints", {}),
                "provenance": provenance,
            }
            params = {
                "packet_id": header["packet_id"],
                "task_id": header["task_id"],
                "task_type": header["task_type"],
                "created_at": datetime.fromisoformat(header["created_at"]),
                "privacy": header["privacy"],
                "remote_allowed": policy.get("remote_allowed", False),
                "packet_hash": provenance.get("packet_hash", ""),
                "cache_key": provenance.get("cache_key", ""),
                "tokens_est": build_stats.get("tokens_total", 0),
                "size_bytes": size_bytes,
                "build_ms": build_stats.get("duration_ms", 0),
                "items_count": len(packet.get("context", [])),
                "redactions_count": len(policy.get("redactions_applied", [])),
                "path": file_path,
                "metadata": json.dumps(metadata_payload),
                "builder_version": header["builder_version"],
            }
            await self.db.execute(query, params)
            await self.db.commit()
            logger.info("Saved packet metadata: %s", header["packet_id"])
            return True
        except Exception as e:
            logger.error("Failed to save packet metadata: %s", e)
            return False

    # ID: 802e8b85-de1b-4980-ac16-106a5b685e75
    async def get_packet_by_id(self, packet_id: str) -> dict[str, Any] | None:
        """Retrieve packet metadata by ID."""
        if not self.db:
            return None
        try:
            query = text(
                "SELECT * FROM core.context_packets WHERE packet_id = :packet_id"
            )
            result = await self.db.execute(query, {"packet_id": packet_id})
            row = result.mappings().first()
            return dict(row) if row else None
        except Exception as e:
            logger.error("Failed to retrieve packet: %s", e)
            return None

    # ID: bec04956-5a41-4907-9c09-1bcf678984a3
    async def get_packets_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Retrieve all packets for a task."""
        if not self.db:
            return []
        try:
            query = text(
                "SELECT * FROM core.context_packets WHERE task_id = :task_id ORDER BY created_at DESC"
            )
            result = await self.db.execute(query, {"task_id": task_id})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error("Failed to retrieve packets for task: %s", e)
            return []

    # ID: 7cdae872-a510-42d0-86a1-01c3bb52848b
    async def get_recent_packets(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve most recent packets."""
        if not self.db:
            return []
        try:
            query = text(
                "SELECT * FROM core.context_packets ORDER BY created_at DESC LIMIT :limit"
            )
            result = await self.db.execute(query, {"limit": limit})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error("Failed to retrieve recent packets: %s", e)
            return []

    # ID: 6ca9f826-a171-4a09-b087-153a6fe3cd81
    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics on packets."""
        if not self.db:
            return {}
        try:
            query = text(
                "\n                SELECT\n                    COUNT(*) as total_packets, COUNT(DISTINCT task_id) as unique_tasks,\n                    AVG(tokens_est) as avg_tokens, AVG(build_ms) as avg_build_ms,\n                    AVG(items_count) as avg_items, SUM(redactions_count) as total_redactions\n                FROM core.context_packets\n            "
            )
            result = await self.db.execute(query)
            row = result.mappings().first()
            return dict(row) if row else {}
        except Exception as e:
            logger.error("Failed to retrieve stats: %s", e)
            return {}
