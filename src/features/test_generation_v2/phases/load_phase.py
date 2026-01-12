# src/features/test_generation_v2/phases/load_phase.py
"""Load phase - initializes ContextService with proper dependency injection."""

from __future__ import annotations

from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
class LoadPhase:
    """Initializes ContextService with cognitive and vector services."""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 946aa269-a5f7-4f95-9836-e7c418bfbf56
    async def execute(self) -> ContextService | None:
        """
        Initialize ContextService with proper DI.

        Returns:
            ContextService instance or None on failure
        """
        try:
            cognitive_service = await self.context.registry.get_cognitive_service()

            qdrant_service = None
            try:
                qdrant_service = await self.context.registry.get_qdrant_service()
            except Exception:
                logger.warning("Qdrant not available - semantic search disabled")

            # Resolve session factory via the registry (primed by Sanctuary)
            context_service = ContextService(
                qdrant_client=qdrant_service,
                cognitive_service=cognitive_service,
                project_root=str(self.context.git_service.repo_path),
                # DI FIX: Use the late-binding factory from the registry
                session_factory=self.context.registry.session,
            )

            logger.info("✅ Load Phase: ContextService initialized")
            return context_service

        except Exception as e:
            logger.error("Load Phase Failed: %s", e, exc_info=True)
            return None
