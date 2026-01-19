# src/will/tools/context/embedding_search.py

"""
Embedding-based search for code examples.
"""

from __future__ import annotations

from qdrant_client import models as qm

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e876db63-b04c-4abc-89ce-84c6ec4e6259
class EmbeddingSearchService:
    """Handles semantic search using embeddings and Qdrant."""

    def __init__(self, cognitive_service, qdrant_service):
        self.cog = cognitive_service
        self.qdrant = qdrant_service

    # ID: 19283410-ad51-481a-afd7-f3f859921aba
    async def search_by_layer(
        self, goal: str, layer: str, limit: int = 10
    ) -> list[dict]:
        """
        Search for code examples in a specific architectural layer.

        Args:
            goal: Search query text
            layer: Architectural layer to filter by
            limit: Maximum number of results

        Returns:
            List of search hits with payload data
        """
        if not self.cog or not self.qdrant:
            logger.warning("Cognitive or Qdrant service not available")
            return []

        embedding = await self.cog.get_embedding_for_code(goal)
        if not embedding:
            logger.warning("Failed to generate embedding for goal")
            return []

        layer_filter = self._build_layer_filter(layer)

        hits = await self.qdrant.search_similar(
            query_vector=embedding, limit=limit, filter_=layer_filter
        )

        return hits or []

    @staticmethod
    def _build_layer_filter(layer: str) -> qm.Filter:
        """Build Qdrant filter for architectural layer."""
        return qm.Filter(
            must=[
                qm.FieldCondition(
                    key="metadata.layer", match=qm.MatchValue(value=layer)
                )
            ]
        )

    @staticmethod
    # ID: 6fb05e84-b58f-4f32-8ded-2ea06ee81d8a
    def extract_symbol_ids(hits: list[dict]) -> list[str]:
        """Extract symbol IDs from search hits."""
        return [
            h["payload"]["symbol_id"]
            for h in hits
            if h.get("payload", {}).get("symbol_id")
        ]
