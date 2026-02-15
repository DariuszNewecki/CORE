# src/will/agents/conversational/factory.py

"""
Factory function for creating ConversationalAgent instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.infrastructure.context.builder import ContextBuilder
from shared.logger import getLogger


if TYPE_CHECKING:
    from .agent import ConversationalAgent

logger = getLogger(__name__)


# Factory function for CLI to create agent instance
# ID: 5a27c5ff-4155-4257-8bfa-9971c3db9395
# ID: eb02dca7-4d71-4a04-a65e-a1ce77122bbf
async def create_conversational_agent() -> ConversationalAgent:
    """
    Factory to create a ConversationalAgent with all dependencies wired.

    This is the composition root for the conversational interface.
    Uses CORE's existing service registry and dependency injection patterns.

    Returns:
        Fully initialized ConversationalAgent
    """
    from body.services.service_registry import service_registry
    from shared.infrastructure.context.providers import DBProvider, VectorProvider

    from .agent import ConversationalAgent

    # Get or create CognitiveService from registry (singleton pattern)
    cognitive_service = await service_registry.get_cognitive_service()

    # Get Qdrant client if available and wrap it in VectorProvider
    vector_provider = None
    try:
        qdrant_client = await service_registry.get_qdrant_service()
        # VectorProvider wraps QdrantService and provides the interface ContextBuilder expects
        vector_provider = VectorProvider(
            qdrant_client=qdrant_client,
            cognitive_service=cognitive_service,
        )
        logger.info("Vector search enabled via Qdrant")
    except Exception as e:
        logger.warning("Qdrant not available: %s. Context search will be limited", e)

    # Create DBProvider - it handles sessions internally
    db_provider = DBProvider()

    # Create ContextBuilder with available services
    context_builder = ContextBuilder(
        db_provider=db_provider,
        vector_provider=vector_provider,  # Now properly wrapped
        ast_provider=None,  # Not used in current implementation
        config={},
    )

    # Create and return agent
    agent = ConversationalAgent(
        context_builder=context_builder,
        cognitive_service=cognitive_service,
    )

    logger.info("ConversationalAgent created successfully")
    return agent
