# src/services/context/providers/vectors.py

"""VectorProvider - Semantic search via Qdrant.

Wraps existing Qdrant client for context building.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ID: f1cfae96-7321-4cab-be1e-f393dc8df33c
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

    # ID: 604998db-001a-480b-8265-820666ae7f49
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
        logger.info(f"Searching Qdrant for: '{query}' (top {top_k})")

        if not self.qdrant:
            logger.warning("No Qdrant client - returning empty results")
            return []

        if not self.cognitive_service:
            logger.warning("No CognitiveService - cannot generate embeddings")
            return []

        try:
            # Generate embedding for the query text
            query_vector = await self.cognitive_service.get_embedding_for_code(query)
            if not query_vector:
                logger.warning("Failed to generate query embedding")
                return []

            # Search using the embedding
            return await self.search_by_embedding(query_vector, top_k, collection)

        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

    # ID: b946488a-5c28-4ff0-b010-b1235e954b66
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
        logger.debug(f"Searching by embedding (top {top_k})")

        if not self.qdrant:
            return []

        try:
            results = await self.qdrant.search_similar(
                query_vector=embedding,
                limit=top_k,
                with_payload=True,
            )

            items = []
            for hit in results:
                payload = hit.get("payload", {})
                score = hit.get("score", 0.0)

                # Extract meaningful fields from payload
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

            logger.info(f"Found {len(items)} similar items from Qdrant")
            return items

        except Exception as e:
            logger.error(f"Qdrant embedding search failed: {e}", exc_info=True)
            return []

    # ID: 6907b4cb-2cec-4bfb-9fe1-c112c76ce155
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
            logger.error(f"Failed to get symbol embedding: {e}")
            return None

    # ID: 41bfcc74-0d0e-48b0-ab18-6b2000548ff0
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
        logger.debug(f"Finding neighbors for: {symbol_name}")

        if not self.qdrant:
            return []

        # This requires looking up the symbol's vector first
        # Skipping for now - needs symbol->vector_id mapping from DB
        logger.warning("get_neighbors not yet implemented - needs DB integration")
        return []
