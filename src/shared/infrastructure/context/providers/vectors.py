# src/shared/infrastructure/context/providers/vectors.py

"""VectorProvider - Semantic search via Qdrant.

Wraps existing Qdrant client for context building.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from typing import Any


logger = logging.getLogger(__name__)


# ID: cd6237eb-1ab0-4488-95df-31092411019c
class VectorProvider:
    """Provides semantic search via Qdrant."""

    def __init__(self, qdrant_client=None, cognitive_service=None):
        """Initialize with Qdrant client and cognitive service.

        Args:
            qdrant_client: QdrantService instance
            cognitive_service: CognitiveService instance for embeddings
        """
        self.qdrant = qdrant_client
        self.cognitive_service = cognitive_service

    # ID: 3ca68418-6be2-4068-b05d-56c4b1191b3d
    async def search_similar(
        self, query: str, top_k: int = 10, collection: str = "code_symbols"
    ) -> list[dict[str, Any]]:
        """Search for semantically similar items.

        Args:
            query: Search query text
            top_k: Number of results
            collection: Qdrant collection name (unused, uses client's default)

        Returns:
            List of similar items with name, path, score, summary
        """
        logger.info("Searching Qdrant for: '{query}' (top %s)", top_k)
        if not self.qdrant:
            logger.warning("No Qdrant client - returning empty results")
            return []
        if not self.cognitive_service:
            logger.warning("No CognitiveService - cannot generate embeddings")
            return []
        try:
            query_vector = await self.cognitive_service.get_embedding_for_code(query)
            if not query_vector:
                logger.warning("Failed to generate query embedding")
                return []
            return await self.search_by_embedding(query_vector, top_k, collection)
        except Exception as e:
            logger.error("Qdrant search failed: %s", e)
            return []

    # ID: 90847657-c290-48cf-9b3a-429f37b26786
    async def search_by_embedding(
        self, embedding: list[float], top_k: int = 10, collection: str = "code_symbols"
    ) -> list[dict[str, Any]]:
        """Search using pre-computed embedding.

        Args:
            embedding: Query embedding vector
            top_k: Number of results
            collection: Qdrant collection name (unused)

        Returns:
            List of similar items
        """
        logger.debug("Searching by embedding (top %s)", top_k)
        if not self.qdrant:
            return []
        try:
            results = await self.qdrant.search_similar(
                query_vector=embedding, limit=top_k, with_payload=True
            )
            items = []
            for hit in results:
                payload = hit.get("payload", {})
                score = hit.get("score", 0.0)
                items.append(
                    {
                        "name": payload.get(
                            "symbol_path", payload.get("chunk_id", "unknown")
                        ),
                        "path": payload.get("file_path", ""),
                        "item_type": "symbol",
                        "summary": payload.get("content", "")[:200],
                        "score": score,
                        "source": "qdrant",
                        "metadata": {
                            "chunk_id": payload.get("chunk_id"),
                            "model": payload.get("model"),
                        },
                    }
                )
            logger.info("Found %s similar items from Qdrant", len(items))
            return items
        except Exception as e:
            logger.error("Qdrant embedding search failed: %s", e, exc_info=True)
            return []

    # ID: 96844a9d-5c4c-4c98-b245-b329e344973c
    async def get_symbol_embedding(self, symbol_id: str) -> list[float] | None:
        """Get embedding for a symbol by its vector ID.

        Args:
            symbol_id: Vector point ID in Qdrant

        Returns:
            Embedding vector or None
        """
        if not self.qdrant:
            return None
        try:
            return await self.qdrant.get_vector_by_id(symbol_id)
        except Exception as e:
            logger.error("Failed to get symbol embedding: %s", e)
            return None

    # ID: 8ae4adb2-18a5-4f06-a0c9-0e6c5b0996a2
    async def get_neighbors(
        self, symbol_name: str, max_distance: float = 0.5, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Get semantic neighbors of a symbol.

        Args:
            symbol_name: Symbol to find neighbors for
            max_distance: Maximum embedding distance (lower score = closer)
            top_k: Number of neighbors

        Returns:
            List of neighbor symbols
        """
        logger.debug("Finding neighbors for: %s", symbol_name)
        if not self.qdrant:
            return []
        logger.warning("get_neighbors not yet implemented - needs DB integration")
        return []
