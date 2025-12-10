# src/will/orchestration/cognitive_service.py

"""
CognitiveService (Facade)

Orchestrates LLM interactions by delegating to the ClientOrchestrator.
Refactored for CORE v2: Removes "Split-Brain" by deleting internal factory logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.llm.client import LLMClient
from shared.infrastructure.llm.client_orchestrator import ClientOrchestrator
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.clients.qdrant_client import QdrantService

logger = getLogger(__name__)


# ID: 159942bd-7c62-45eb-83a6-5b531ae7e172
class CognitiveService:
    """
    Facade for AI capabilities.

    Responsibilities:
    1. Delegate client acquisition to ClientOrchestrator (The Will).
    2. Provide high-level semantic search via Qdrant (The Mind's Index).
    """

    def __init__(self, repo_path: Path, qdrant_service: QdrantService | None = None):
        """
        Initialize CognitiveService.

        Args:
            repo_path: Path to the repository root.
            qdrant_service: Singleton QdrantService instance (Injected).
        """
        self._repo_path = Path(repo_path)

        # THE BRAIN: Use the centralized ClientOrchestrator
        self.client_orchestrator = ClientOrchestrator(self._repo_path)

        # DI: Store the injected service
        self._qdrant_service = qdrant_service

    @property
    # ID: 940cd168-7cd4-4572-aeb2-cd6fcebaca39
    def qdrant_service(self) -> QdrantService:
        """Access the injected QdrantService."""
        if self._qdrant_service is None:
            raise RuntimeError(
                "QdrantService was not injected into CognitiveService. "
                "This capability requires a fully wired service via ServiceRegistry."
            )
        return self._qdrant_service

    # ID: 309fe915-a152-4767-b4c3-741d6f7763da
    async def initialize(self) -> None:
        """Initialize the orchestrator (load Mind state from DB)."""
        await self.client_orchestrator.initialize()

    # ID: c7ecbba2-6b3d-4d79-b66f-5d9d34ee1d98
    async def aget_client_for_role(self, role_name: str) -> LLMClient:
        """
        Get an LLM client for a specific role.
        Delegates decision-making to ClientOrchestrator.
        """
        return await self.client_orchestrator.get_client_for_role(role_name)

    # ID: 32acb8d7-a0dc-402c-82e7-4d4a8e91c9f8
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate an embedding using the Vectorizer role."""
        if not source_code:
            return None
        # Go through the orchestrator to get the correct client
        client = await self.aget_client_for_role("Vectorizer")
        return await client.get_embedding(source_code)

    # ID: 3e79bb9c-c711-42d5-8781-bd155913018c
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search via Qdrant."""
        # Ensure orchestrator is initialized (it manages the Vectorizer client)
        if not self.client_orchestrator._loaded:
            await self.initialize()

        try:
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                return []
            return await self.qdrant_service.search_similar(query_vector, limit=limit)
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            return []

    # DELETED: _create_provider_for_resource
    # DELETED: _config_cache (managed by Orchestrator/Registry now)
    # DELETED: _resources, _roles (managed by Orchestrator now)
