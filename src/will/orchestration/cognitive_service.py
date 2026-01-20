# src/will/orchestration/cognitive_service.py
"""
CognitiveService (Facade)
Orchestrates LLM interactions by delegating to the ClientOrchestrator.
UPGRADED: Supports High-Reasoning Escalation Tier.
Constitutional Compliance:
- Will layer: Orchestrates cognitive operations and client selection
- Mind/Body/Will separation: Creates MindStateService during initialize()
- No direct database access: Uses service_registry.session() for initialization
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.llm.client import LLMClient
from shared.logger import getLogger
from will.orchestration.client_orchestrator import ClientOrchestrator


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
    3. Support tiered reasoning escalation.

    Constitutional Note:
    ClientOrchestrator is created during initialize() when session is available.
    No direct instantiation in __init__ to avoid violating Mind/Body/Will separation.
    """

    def __init__(self, repo_path: Path, qdrant_service: QdrantService | None = None):
        """
        Initialize CognitiveService.

        Args:
            repo_path: Repository root path
            qdrant_service: Optional QdrantService for semantic search

        Constitutional Note:
        ClientOrchestrator is NOT created here - it requires MindStateService
        which needs a database session. Created during initialize() instead.
        """
        self._repo_path = Path(repo_path)
        self.client_orchestrator: ClientOrchestrator | None = None
        self._qdrant_service = qdrant_service

    @property
    # ID: 76839929-7e48-4592-b377-1401ad9b9d30
    def qdrant_service(self) -> QdrantService:
        """Access the injected QdrantService."""
        if self._qdrant_service is None:
            raise RuntimeError("QdrantService was not injected into CognitiveService.")
        return self._qdrant_service

    # ID: 2cee004a-5a80-421d-a5cc-c2f3e07c99e0
    async def initialize(self) -> None:
        """
        Initialize the orchestrator (load Mind state from DB).

        Constitutional Note:
        This is where we create ClientOrchestrator with MindStateService.
        We create a temporary session to bootstrap MindStateService,
        then pass it to ClientOrchestrator which caches Mind state.
        """
        if self.client_orchestrator is not None:
            # Already initialized
            await self.client_orchestrator.initialize()
            return

        # Constitutional compliance: Create MindStateService with session
        from body.services.mind_state_service import MindStateService
        from body.services.service_registry import service_registry

        async with service_registry.session() as session:
            mind_state_service = MindStateService(session)

            # Create ClientOrchestrator with MindStateService
            self.client_orchestrator = ClientOrchestrator(
                self._repo_path, mind_state_service
            )

            # Initialize to load Mind state while session is available
            await self.client_orchestrator.initialize()

    # ID: 7a0c5b7d-a434-4897-910b-060560ba176e
    async def aget_client_for_role(
        self, role_name: str, high_reasoning: bool = False
    ) -> LLMClient:
        """
        Get an LLM client for a specific role.

        Args:
            role_name: The target role (e.g., 'Coder')
            high_reasoning: If True, attempts to escalate to the 'Architect' role.
        """
        if self.client_orchestrator is None:
            await self.initialize()

        target_role = role_name

        if high_reasoning:
            logger.info(
                "🚀 ECOLOGY: Escalating to High-Reasoning Tier for role '%s'", role_name
            )
            target_role = "Architect"  # Constitutionally mapped to high-tier models

        try:
            return await self.client_orchestrator.get_client_for_role(target_role)
        except Exception as e:
            if target_role == "Architect":
                logger.warning(
                    "⚠️ Escalation failed (Architect role unconfigured). Falling back to %s: %s",
                    role_name,
                    e,
                )
                return await self.client_orchestrator.get_client_for_role(role_name)
            raise

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
        if self.client_orchestrator is None or not self.client_orchestrator._loaded:
            await self.initialize()
        try:
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                return []
            return await self.qdrant_service.search_similar(query_vector, limit=limit)
        except Exception as e:
            logger.error("Semantic search failed: %s", e, exc_info=True)
            return []

    @staticmethod
    def _create_provider_for_resource_static(resource):
        """
        Static factory for provider creation.
        Used by ClientOrchestrator's provider_factory callback.

        Constitutional Note:
        This is a workaround for circular dependency between
        CognitiveService and ClientOrchestrator. Should be refactored.
        """
        # This method is called by ClientOrchestrator internally
        # Implementation moved there to avoid circular dependency
        raise NotImplementedError(
            "Provider creation moved to ClientOrchestrator._create_provider_for_resource"
        )


# Constitutional Note:
# This refactoring delays ClientOrchestrator creation until initialize()
# when we have a database session to create MindStateService.
# The session is temporary - MindStateService loads data and caches it,
# so ClientOrchestrator doesn't need the session after initialization.
