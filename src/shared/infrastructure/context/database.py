# src/shared/infrastructure/context/database.py

"""ContextDatabase - persistence layer for context packet metadata."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 9871ed94-1611-429b-a12b-63eb65417a23
class ContextDatabase:
    """Manages database persistence for context packet metadata."""

    def __init__(self) -> None:
        self.db: AsyncSession | None = None

    # ID: 5f8732e6-89d2-4652-bfce-c112773142ce
    async def save_packet_metadata(
        self,
        packet: dict[str, Any],
        file_path: str,
        size_bytes: int,
    ) -> bool:
        if not self.db:
            logger.warning("No database service - skipping metadata save")
            return False

        try:
            header = packet.get("header", {})
            policy = packet.get("policy", {})
            provenance = packet.get("provenance", {})
            build_stats = provenance.get("build_stats", {})

            query = text(
                """
                INSERT INTO core.context_packets (
                    packet_id,
                    task_id,
                    task_type,
                    created_at,
                    privacy,
                    remote_allowed,
                    packet_hash,
                    cache_key,
                    tokens_est,
                    size_bytes,
                    build_ms,
                    items_count,
                    redactions_count,
                    path,
                    metadata,
                    builder_version
                ) VALUES (
                    :packet_id,
                    :task_id,
                    :task_type,
                    :created_at,
                    :privacy,
                    :remote_allowed,
                    :packet_hash,
                    :cache_key,
                    :tokens_est,
                    :size_bytes,
                    :build_ms,
                    :items_count,
                    :redactions_count,
                    :path,
                    :metadata,
                    :builder_version
                )
                """
            )

            metadata_payload = {
                "goal": header.get("goal"),
                "trigger": header.get("trigger"),
                "phase": packet.get("phase"),
                "constraints": packet.get("constraints", {}),
                "provenance": provenance,
                "runtime": packet.get("runtime", {}),
            }

            params = {
                "packet_id": header.get("packet_id"),
                "task_id": header.get("packet_id"),
                "task_type": "context_packet",
                "created_at": datetime.fromisoformat(header["created_at"]),
                "privacy": header.get("privacy", "local_only"),
                "remote_allowed": policy.get("remote_allowed", False),
                "packet_hash": provenance.get("packet_hash", ""),
                "cache_key": provenance.get("cache_key", ""),
                "tokens_est": build_stats.get("tokens_total", 0),
                "size_bytes": size_bytes,
                "build_ms": build_stats.get("duration_ms", 0),
                "items_count": len(packet.get("evidence", [])),
                "redactions_count": len(provenance.get("redactions_applied", [])),
                "path": file_path,
                "metadata": json.dumps(metadata_payload),
                "builder_version": header.get("builder_version", ""),
            }

            await self.db.execute(query, params)
            await self.db.commit()
            logger.info("Saved packet metadata: %s", params["packet_id"])
            return True

        except Exception as e:
            logger.error("Failed to save packet metadata: %s", e)
            return False

    # ID: 37531758-fd1a-4dee-baff-073dd2ee3e82
    async def get_packet_by_id(self, packet_id: str) -> dict[str, Any] | None:
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

    # ID: e7ac28bc-e386-40e5-b91f-9ae6f83c318a
    async def get_packets_for_task(self, task_id: str) -> list[dict[str, Any]]:
        if not self.db:
            return []

        try:
            query = text(
                """
                SELECT *
                FROM core.context_packets
                WHERE task_id = :task_id
                ORDER BY created_at DESC
                """
            )
            result = await self.db.execute(query, {"task_id": task_id})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error("Failed to retrieve packets for task: %s", e)
            return []

    # ID: ddfcb345-a644-4339-8f67-18ac17cc26f5
    async def get_recent_packets(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.db:
            return []

        try:
            query = text(
                """
                SELECT *
                FROM core.context_packets
                ORDER BY created_at DESC
                LIMIT :limit
                """
            )
            result = await self.db.execute(query, {"limit": limit})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error("Failed to retrieve recent packets: %s", e)
            return []

    # ID: 7dd22172-8894-4835-a8f8-d854d4a2051b
    async def get_stats(self) -> dict[str, Any]:
        if not self.db:
            return {}

        try:
            query = text(
                """
                SELECT
                    COUNT(*) AS total_packets,
                    COUNT(DISTINCT task_id) AS unique_tasks,
                    AVG(tokens_est) AS avg_tokens,
                    AVG(build_ms) AS avg_build_ms,
                    AVG(items_count) AS avg_items,
                    SUM(redactions_count) AS total_redactions
                FROM core.context_packets
                """
            )
            result = await self.db.execute(query)
            row = result.mappings().first()
            return dict(row) if row else {}
        except Exception as e:
            logger.error("Failed to retrieve stats: %s", e)
            return {}
