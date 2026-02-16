# src/shared/infrastructure/context/service.py
"""
ContextService - Main orchestrator for ContextPackage lifecycle.

Supports sensory injection via LimbWorkspace for "future truth" context.
Coordinates the transition between Historical State (DB) and Shadow State (Workspace).

HEALED (V2.3.0):
- JIT Service Resolution: Now resolves Cognitive and Qdrant services from the
  global registry at runtime if they were provided as None during bootstrap.
- Prevents 'Two Brains' bug while preserving all V2.3.0 query-parsing features.
"""

from __future__ import annotations

import uuid
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
        self._session_factory = session_factory
        self.workspace = workspace

        # Store these privately; they might be None if called from bootstrap factory
        self._qdrant_client = qdrant_client
        self._cognitive_service = cognitive_service

        # Initialize core components that don't need the "Brain" yet
        self.validator = ContextValidator()
        self.redactor = ContextRedactor()
        self.cache = ContextCache(self.config.get("cache_dir", "work/context_cache"))
        self.database = ContextDatabase()
        self.ast_provider = ASTProvider(project_root)

        if self.workspace:
            logger.info(
                "ContextService initialized in SHADOW mode (Future Truth active)"
            )

    # ID: 498ac646-47e9-4e86-83b0-e25923ff9ef5
    async def build_for_task(
        self, task_spec: dict[str, Any], use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Build a context packet for a task.
        CONSTITUTIONAL FIX: Resolves Brain and Memory JIT to ensure they are initialized.
        """
        # 1. THE MERGE: If we are missing services, grab the Global ones from the Registry
        if self._cognitive_service is None or self._qdrant_client is None:
            from body.services.service_registry import service_registry

            if self._cognitive_service is None:
                self._cognitive_service = await service_registry.get_cognitive_service()
            if self._qdrant_client is None:
                self._qdrant_client = await service_registry.get_qdrant_service()

        # 2. THE RE-WIRING: Ensure Providers use the AWAKE Brain
        db_provider = DBProvider(session_factory=self._session_factory)
        vector_provider = VectorProvider(self._qdrant_client, self._cognitive_service)

        builder = ContextBuilder(
            db_provider,
            vector_provider,
            self.ast_provider,
            self.config,
            workspace=self.workspace,
        )

        # 3. Cache Logic
        effective_use_cache = use_cache if self.workspace is None else False
        if effective_use_cache:
            cache_key = ContextSerializer.compute_cache_key(task_spec)
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # 4. Execute the build (This now has access to the awake Brain)
        packet = await builder.build_for_task(task_spec)

        # 5. Validation and Redaction
        result = self.validator.validate(packet)
        if not result.ok:
            logger.error("Context Packet rejected: %s", result.errors)
            raise ValueError(f"Context validation failed: {result.errors}")

        packet = self.redactor.redact(result.validated_data)
        packet["provenance"]["packet_hash"] = ContextSerializer.compute_packet_hash(
            packet
        )

        return packet

    # ID: 512bfbd1-2a03-4eec-aff5-64d8bf344d43
    async def build_from_query(
        self,
        natural_query: str,
        max_tokens: int = 30000,
        max_items: int = 30,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        Build context package from natural language query.
        PRESERVED: Full V2.3.0 classification logic.
        """
        logger.info("Building context from query: '%s'", natural_query)

        query_type = self._classify_query(natural_query)
        logger.debug("Query classified as: %s", query_type)

        scope = self._extract_scope(natural_query, query_type)

        task_spec = {
            "task_id": f"query_{uuid.uuid4().hex[:8]}",
            "task_type": "code_search",
            "summary": natural_query,
            "scope": scope,
            "constraints": {
                "max_tokens": max_tokens,
                "max_items": max_items,
            },
        }

        return await self.build_for_task(task_spec, use_cache=use_cache)

    def _classify_query(self, query: str) -> str:
        """Pattern indicators: specific code constructs"""
        pattern_keywords = [
            "isinstance",
            "import",
            "async",
            "with",
            "try",
            "except",
            "class",
            "def",
            "await",
            "yield",
            "lambda",
        ]
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in pattern_keywords):
            return "pattern"
        if any(phrase in query_lower for phrase in ["uses", "calls", "contains"]):
            return "pattern"
        return "semantic"

    def _extract_scope(self, query: str, query_type: str) -> dict[str, Any]:
        """Extract search scope from natural language query."""
        scope: dict[str, Any] = {
            "include": [],
            "exclude": ["tests/", "migrations/", "__pycache__"],
            "traversal_depth": 0,
        }

        query_lower = query.lower()
        if query_type == "pattern":
            pattern_keywords = [
                "isinstance",
                "async",
                "await",
                "with",
                "try",
                "except",
                "class",
                "def",
                "import",
                "lambda",
                "yield",
            ]
            for keyword in pattern_keywords:
                if keyword in query_lower:
                    scope["include"].append(keyword)
            scope["traversal_depth"] = 1

        common_terms = ["in", "from", "within", "inside", "under"]
        for term in common_terms:
            if f" {term} " in f" {query_lower} ":
                parts = query_lower.split(term)
                if len(parts) > 1:
                    potential_scope = parts[1].strip().split()[0]
                    if potential_scope not in ["the", "a", "an", "all", "any"]:
                        scope["include"].append(potential_scope)

        return scope
