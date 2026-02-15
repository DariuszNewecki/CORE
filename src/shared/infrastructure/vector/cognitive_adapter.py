# src/shared/infrastructure/vector/cognitive_adapter.py
# ID: b2601572-9c8a-44e6-9a68-836d7535cb16
"""
CognitiveService Adapter for VectorIndexService

Adapts CognitiveService to the Embeddable protocol so it can be used
with VectorIndexService for smart deduplication.

This allows constitutional vectorization to use the same embedding provider
as code vectorization (database-configured LLM) instead of requiring
separate local embedding settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 879b1a9a-23db-40f3-ae35-86853dff835a
# ID: b4c348a3-9d0e-4079-a6bd-eb93be95686f
class CognitiveEmbedderAdapter:
    """
    Adapts CognitiveService to the Embeddable protocol.

    This allows VectorIndexService to use CognitiveService for embeddings,
    enabling constitutional documents to use the same embedding provider
    as code symbols (database-configured, not environment-based).

    Usage:
        cognitive_service = await registry.get_cognitive_service()
        embedder = CognitiveEmbedderAdapter(cognitive_service)

        service = VectorIndexService(
            qdrant_service=qdrant,
            collection_name="core_policies",
            embedder=embedder  # ← Inject CognitiveService!
        )

        # Now uses smart deduplication + database-configured embeddings
        await service.index_items(policy_items)
    """

    def __init__(self, cognitive_service: CognitiveService):
        """
        Initialize adapter.

        Args:
            cognitive_service: Initialized CognitiveService instance
        """
        self._cognitive_service = cognitive_service
        logger.debug("CognitiveEmbedderAdapter initialized")

    # ID: d494615f-51d5-4796-a62a-ddf9e3e7bda3
    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding using CognitiveService.

        This delegates to cognitive_service.get_embedding_for_code() which
        uses the database-configured LLM provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            RuntimeError: If embedding generation fails
        """
        try:
            embedding = await self._cognitive_service.get_embedding_for_code(text)

            if not embedding:
                raise RuntimeError("CognitiveService returned empty embedding")

            return embedding

        except Exception as e:
            logger.error("Failed to generate embedding via CognitiveService: %s", e)
            raise RuntimeError(f"Embedding generation failed: {e}") from e
