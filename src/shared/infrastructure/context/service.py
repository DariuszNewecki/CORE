# src/shared/infrastructure/context/service.py
"""
ContextService - Main orchestrator for ContextPackage lifecycle.

Supports sensory injection via LimbWorkspace for "future truth" context.
Coordinates the transition between Historical State (DB) and Shadow State (Workspace).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger

from .builder import ContextBuilder
from .cache import ContextCache
from .database import ContextDatabase
from .providers.ast import ASTProvider
from .providers.db import DBProvider
from .providers.vectors import VectorProvider
from .redactor import ContextRedactor
from .serializers import ContextSerializer
from .validator import ContextValidator


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


# ID: 6fee4321-e9f8-4234-b9f0-dbe2c49ec016
class ContextService:
    """
    Main service for ContextPackage lifecycle management.

    Constitutional Role: Infrastructure Coordination.
    Acts as the sensory nerve center for AI agents.
    """

    def __init__(
        self,
        qdrant_client: Any | None = None,
        cognitive_service: Any | None = None,
        config: dict[str, Any] | None = None,
        project_root: str = ".",
        session_factory: Any | None = None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.config = config or {}
        self.project_root = Path(project_root)
        self.cognitive_service = cognitive_service
        self._session_factory = session_factory
        self.workspace = workspace

        # CONSTITUTIONAL FIX: Pass the session factory to the DB provider.
        # This allows the Body to read Historical Truth when the Shadow view is insufficient.
        self.db_provider = DBProvider(session_factory=self._session_factory)

        self.vector_provider = VectorProvider(qdrant_client, cognitive_service)
        self.ast_provider = ASTProvider(project_root)

        # The Builder is the 'Frontal Lobe' that decides which truth to prioritize.
        self.builder = ContextBuilder(
            self.db_provider,
            self.vector_provider,
            self.ast_provider,
            self.config,
            workspace=self.workspace,
        )

        self.validator = ContextValidator()
        self.redactor = ContextRedactor()
        self.cache = ContextCache(self.config.get("cache_dir", "work/context_cache"))
        self.database = ContextDatabase()

        if self.workspace:
            logger.info(
                "ContextService initialized in SHADOW mode (Future Truth active)"
            )

    # ID: 498ac646-47e9-4e86-83b0-e25923ff9ef5
    async def build_for_task(
        self, task_spec: dict[str, Any], use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Build a context packet for a task, optionally using cached content.

        SAFETY: If a workspace is present, caching is ALWAYS disabled to
        prevent "Hallucination by Stale Memory."
        """
        effective_use_cache = use_cache if self.workspace is None else False

        if effective_use_cache:
            cache_key = ContextSerializer.compute_cache_key(task_spec)
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Orchestrate the build (Delegates to ContextBuilder)
        packet = await self.builder.build_for_task(task_spec)

        # Constitutional Validation
        result = self.validator.validate(packet)
        if not result.ok:
            logger.error("Context Packet rejected: %s", result.errors)
            raise ValueError(f"Context validation failed: {result.errors}")

        # Policy-Based Redaction
        packet = self.redactor.redact(result.validated_data)

        # Identity Finalization
        packet["provenance"]["packet_hash"] = ContextSerializer.compute_packet_hash(
            packet
        )

        return packet
