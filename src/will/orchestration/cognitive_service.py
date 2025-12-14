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


# ID: f5f23648-26a8-42ba-a489-b51194a87685
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
        self.client_orchestrator = ClientOrchestrator(self._repo_path)
        self._qdrant_service = qdrant_service

    @property
    # ID: 76839929-7e48-4592-b377-1401ad9b9d30
    def qdrant_service(self) -> QdrantService:
        """Access the injected QdrantService."""
        if self._qdrant_service is None:
            raise RuntimeError(
                "QdrantService was not injected into CognitiveService. This capability requires a fully wired service via ServiceRegistry."
            )
        return self._qdrant_service

    # ID: 2cee004a-5a80-421d-a5cc-c2f3e07c99e0
    async def initialize(self) -> None:
        """Initialize the orchestrator (load Mind state from DB)."""
        await self.client_orchestrator.initialize()

    # ID: 7a0c5b7d-a434-4897-910b-060560ba176e
    async def aget_client_for_role(self, role_name: str) -> LLMClient:
        """
        Get an LLM client for a specific role.
        Delegates decision-making to ClientOrchestrator.
        """
        return await self.client_orchestrator.get_client_for_role(role_name)

    # ID: 64a09426-e74e-4547-a08f-3af887085bac
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate an embedding using the Vectorizer role."""
        if not source_code:
            return None
        client = await self.aget_client_for_role("Vectorizer")
        return await client.get_embedding(source_code)

    # ID: 8b9e2ff1-ec8d-4234-b96c-0a2fc1f43804
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search via Qdrant."""
        if not self.client_orchestrator._loaded:
            await self.initialize()
        try:
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                return []
            return await self.qdrant_service.search_similar(query_vector, limit=limit)
        except Exception as e:
            logger.error("Semantic search failed: %s", e, exc_info=True)
            return []
