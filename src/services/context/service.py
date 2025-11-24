# src/services/context/service.py

"""ContextService - Main orchestrator for context packet lifecycle.

Integrates builder, validator, redactor, cache, and database.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from .builder import ContextBuilder
from .cache import ContextCache
from .database import ContextDatabase
from .providers.ast import ASTProvider
from .providers.db import DBProvider
from .providers.vectors import VectorProvider
from .redactor import ContextRedactor
from .reuse import ReuseAnalysis, ReuseFinder
from .serializers import ContextSerializer
from .validator import ContextValidator

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager]


# ID: 6fee4321-e9f8-4234-b9f0-dbe2c49ec016
class ContextService:
    """Main service for ContextPackage lifecycle management."""

    def __init__(
        self,
        qdrant_client: Any | None = None,
        cognitive_service: Any | None = None,
        config: dict[str, Any] | None = None,
        project_root: str = ".",
        session_factory: SessionFactory | None = None,
    ):
        """Initialize context service with dependencies.

        Args:
            qdrant_client: Qdrant client instance.
            cognitive_service: CognitiveService for embeddings.
            config: Configuration dict.
            project_root: Project root directory.
            session_factory: Callable that returns an async DB session context
                manager. If None, DB persistence and stats are skipped.
        """
        self.config = config or {}
        self.project_root = Path(project_root)
        self.cognitive_service = cognitive_service
        self._session_factory = session_factory

        # Initialize providers without a database session.
        self.db_provider = DBProvider()
        self.vector_provider = VectorProvider(qdrant_client, cognitive_service)
        self.ast_provider = ASTProvider(project_root)

        # Initialize components
        self.builder = ContextBuilder(
            self.db_provider,
            self.vector_provider,
            self.ast_provider,
            self.config,
        )
        self.validator = ContextValidator()
        self.redactor = ContextRedactor()
        self.cache = ContextCache(self.config.get("cache_dir", "work/context_cache"))
        self.database = ContextDatabase()

        # Initialize reuse helper (semantic + structural search for reuse-first development).
        self.reuse_finder = ReuseFinder(
            vector_provider=self.vector_provider,
            ast_provider=self.ast_provider,
        )

    # ID: 498ac646-47e9-4e86-83b0-e25923ff9ef5
    async def build_for_task(
        self,
        task_spec: dict[str, Any],
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Build complete context packet for task.

        Full pipeline:
        1. Check cache
        2. Build from providers
        3. Validate
        4. Redact
        5. Compute hashes
        6. Persist to disk & DB
        7. Cache result

        Args:
            task_spec: Task specification
            use_cache: Whether to use cached packets

        Returns:
            Complete, validated, redacted ContextPackage
        """
        logger.info("Building context for task %s", task_spec.get("task_id"))

        if use_cache:
            cache_key = ContextSerializer.compute_cache_key(task_spec)
            cached = self.cache.get(cache_key)
            if cached:
                logger.info("Using cached packet")
                return cached

        packet = await self.builder.build_for_task(task_spec)

        is_valid, errors = self.validator.validate(packet)
        if not is_valid:
            error_msg = f"Validation failed: {errors}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        packet = self.redactor.redact(packet)

        packet["provenance"]["packet_hash"] = ContextSerializer.compute_packet_hash(
            packet
        )
        packet["provenance"]["cache_key"] = ContextSerializer.compute_cache_key(
            task_spec
        )

        task_id = task_spec["task_id"]
        output_dir = self.project_root / "work" / "context_packets" / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "context.yaml"

        ContextSerializer.to_yaml(packet, str(output_path))
        file_size = output_path.stat().st_size

        # Persist metadata to DB if a session factory is available.
        if self._session_factory is not None:
            async with self._session_factory() as db:
                self.database.db = db
                await self.database.save_packet_metadata(
                    packet,
                    str(output_path),
                    file_size,
                )
        else:
            logger.debug(
                "No session_factory configured; skipping DB persistence "
                "for packet %s",
                packet["header"]["packet_id"],
            )

        if use_cache:
            cache_key = packet["provenance"]["cache_key"]
            self.cache.put(cache_key, packet)

        logger.info("Built and persisted packet %s", packet["header"]["packet_id"])
        return packet

    # ID: 1548660f-ebc3-41b0-9427-83f527dbf9b9
    async def load_packet(self, task_id: str) -> dict[str, Any] | None:
        """Load packet from disk by task ID.

        Args:
            task_id: Task identifier

        Returns:
            ContextPackage dict or None if not found
        """
        packet_path = (
            self.project_root / "work" / "context_packets" / task_id / "context.yaml"
        )

        if not packet_path.exists():
            logger.warning("Packet not found for task %s", task_id)
            return None

        return ContextSerializer.from_yaml(str(packet_path))

    # ID: 7eb62236-0835-4856-9ac1-1c421f526535
    def validate_packet(self, packet: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a packet against schema.

        Args:
            packet: ContextPackage dict

        Returns:
            Tuple of (is_valid, errors)
        """
        return self.validator.validate(packet)

    # ID: d95ad2a7-1376-4b70-a799-3ce6e33e508c
    async def get_task_packets(self, task_id: str) -> list[dict[str, Any]]:
        """Get all packets for a task from database.

        Args:
            task_id: Task identifier

        Returns:
            List of packet metadata dicts
        """
        if self._session_factory is None:
            logger.warning(
                "No session_factory configured; cannot load task packets for %s",
                task_id,
            )
            return []

        async with self._session_factory() as db:
            self.database.db = db
            return await self.database.get_packets_for_task(task_id)

    # ID: ab7a9ff9-c733-4867-8d4a-fac12672096d
    async def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics dict
        """
        if self._session_factory is None:
            logger.warning(
                "No session_factory configured; returning empty stats "
                "because no session_factory is configured.",
            )
            return {}

        async with self._session_factory() as db:
            self.database.db = db
            return await self.database.get_stats()

    # ID: 57f88e39-69b5-4b9d-9a78-52f2ce4bfa45
    async def get_reuse_analysis(self, goal: str) -> ReuseAnalysis:
        """Return reuse analysis for a given goal.

        This method composes semantic and structural search results to support
        reuse-first development. It does not perform any refactoring or make
        decisions; it only exposes data for agents and policies to act on.

        Args:
            goal: Natural-language description of the intended change or feature.

        Returns:
            A ReuseAnalysis instance containing similar symbols, structural
            matches, and available universal helpers.
        """
        return await self.reuse_finder.analyze(goal)

    # ID: 0a767d59-acbc-4c3c-a372-4ef9bf991d2c
    def clear_cache(self) -> int:
        """Clear all cached packets.

        Returns:
            Number of entries removed
        """
        return self.cache.clear_all()
