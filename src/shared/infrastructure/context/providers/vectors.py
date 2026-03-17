# src/shared/infrastructure/context/providers/vectors.py

"""
VectorProvider - semantic evidence retrieval via Qdrant.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6e270409-6fa3-4ef2-a42d-a31e923bac52
class VectorProvider:
    """Provides semantic search evidence via Qdrant."""

    def __init__(
        self,
        qdrant_client: Any | None = None,
        cognitive_service: Any | None = None,
    ) -> None:
        self.qdrant = qdrant_client
        self.cognitive_service = cognitive_service

    # ID: 5c869ad3-729e-4279-b8b1-2d2cc8b21549
    async def search_similar(
        self,
        query: str,
        top_k: int = 10,
        collection: str = "core_capabilities",
    ) -> list[dict[str, Any]]:
        """Search for semantically similar evidence items from a text query."""
        logger.debug("Searching vectors for query '%s' (top_k=%s)", query, top_k)

        if not self.qdrant or not self.cognitive_service:
            logger.warning("Vector infrastructure incomplete - returning empty")
            return []

        try:
            query_vector = await self.cognitive_service.get_embedding_for_code(query)
            if not query_vector:
                logger.warning("Failed to generate embedding for query: %s", query)
                return []

            return await self.search_by_embedding(query_vector, top_k, collection)
        except Exception as e:
            logger.error("Qdrant search failed: %s", e)
            return []

    # ID: 0e8a4841-b1d6-4b73-8fba-f8a34325e0bf
    async def search_by_embedding(
        self,
        embedding: list[float],
        top_k: int = 10,
        collection: str = "core_capabilities",
    ) -> list[dict[str, Any]]:
        """Search using a pre-computed embedding."""
        if not self.qdrant:
            return []

        try:
            results = await self.qdrant.search_similar(
                query_vector=embedding,
                limit=top_k,
                with_payload=True,
            )
            return [self._format_hit(hit) for hit in results]
        except Exception as e:
            logger.error("Qdrant embedding search failed: %s", e, exc_info=True)
            return []

    # ID: da668982-3dbe-49da-953b-9a532cb11617
    async def get_symbol_embedding(self, symbol_id: str) -> list[float] | None:
        """Get stored embedding for a symbol by vector id."""
        if not self.qdrant:
            return None

        try:
            return await self.qdrant.get_vector_by_id(symbol_id)
        except Exception as e:
            logger.debug("Failed to fetch symbol embedding for %s: %s", symbol_id, e)
            return None

    # ID: aa556d35-f222-4e79-9204-b8725feafe50
    async def get_neighbors(
        self,
        symbol_name: str,
        max_distance: float = 0.5,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Get semantic neighbors of a symbol."""
        if not self.cognitive_service or not self.qdrant:
            return []

        try:
            anchor_vec = await self.cognitive_service.get_embedding_for_code(
                symbol_name
            )
            if not anchor_vec:
                return []
        except Exception as e:
            logger.error("Failed to get anchor embedding: %s", e)
            return []

        min_score = 1.0 - max_distance

        try:
            results = await self.qdrant.search_similar(
                query_vector=anchor_vec,
                limit=top_k,
                with_payload=True,
            )

            items: list[dict[str, Any]] = []
            for hit in results:
                score = float(hit.get("score", 0.0))
                if score < min_score:
                    continue

                item = self._format_hit(hit)
                item["distance"] = 1.0 - score
                items.append(item)

            return items
        except Exception as e:
            logger.error("Neighbor search failed: %s", e, exc_info=True)
            return []

    def _format_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Qdrant hit into an evidence item."""
        payload = hit.get("payload", {}) or {}

        file_path = payload.get("source_path") or payload.get("file_path", "")
        symbol_path = payload.get("symbol_path") or payload.get("symbol")
        name = symbol_path or payload.get("chunk_id", "unknown")

        return {
            "name": name,
            "path": file_path,
            "item_type": "semantic_match",
            "content": payload.get("content"),
            "summary": (payload.get("content") or "")[:200],
            "signature": payload.get("signature", ""),
            "score": float(hit.get("score", 0.0)),
            "source": "vector_search",
            "symbol_path": symbol_path,
            "metadata": {
                "chunk_id": payload.get("chunk_id"),
                "collection": payload.get("collection"),
            },
        }
