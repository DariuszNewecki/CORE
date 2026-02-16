# src/shared/infrastructure/context/providers/vectors.py

"""
VectorProvider - Semantic search via Qdrant.

HEALED (V2.3.0):
- Removed 'fail-silent' initialization checks that caused search skips.
- Preserved all 'Smart Implementation' logic for neighbors and embeddings.
- Aligned payload mapping to handle 'source_path' (the new V2.7 standard).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    pass

logger = getLogger(__name__)


# ID: cd6237eb-1ab0-4488-95df-31092411019c
class VectorProvider:
    """Provides semantic search via Qdrant."""

    def __init__(self, qdrant_client=None, cognitive_service=None):
        self.qdrant = qdrant_client
        self.cognitive_service = cognitive_service

    # ID: 3ca68418-6be2-4068-b05d-56c4b1191b3d
    async def search_similar(
        self, query: str, top_k: int = 10, collection: str = "core_capabilities"
    ) -> list[dict[str, Any]]:
        """Search for semantically similar items using text query."""
        logger.info("🧠 Searching Qdrant for: '%s' (top %s)", query, top_k)

        if not self.qdrant or not self.cognitive_service:
            logger.warning("Vector infrastructure incomplete - returning empty")
            return []

        # CONSTITUTIONAL FIX: Removed the '_loaded' check.
        # The ContextService now ensures initialization before calling.

        try:
            query_vector = await self.cognitive_service.get_embedding_for_code(query)
            if not query_vector:
                logger.warning("Failed to generate embedding for query: %s", query)
                return []

            return await self.search_by_embedding(query_vector, top_k, collection)
        except Exception as e:
            logger.error("Qdrant search failed: %s", e)
            return []

    # ID: 90847657-c290-48cf-9b3a-429f37b26786
    async def search_by_embedding(
        self,
        embedding: list[float],
        top_k: int = 10,
        collection: str = "core_capabilities",
    ) -> list[dict[str, Any]]:
        """Search using pre-computed embedding."""
        if not self.qdrant:
            return []
        try:
            results = await self.qdrant.search_similar(
                query_vector=embedding, limit=top_k, with_payload=True
            )
            items = []
            for hit in results:
                payload = hit.get("payload", {})

                # HEALED: Map both old and new path formats so 'sensation' works
                file_path = payload.get("source_path") or payload.get("file_path", "")
                symbol_name = payload.get("symbol") or payload.get(
                    "symbol_path", payload.get("chunk_id", "unknown")
                )

                items.append(
                    {
                        "name": symbol_name,
                        "path": file_path,
                        "item_type": "symbol",
                        "summary": payload.get("content", "")[:200],
                        "score": hit.get("score", 0.0),
                        "source": "qdrant",
                    }
                )
            return items
        except Exception as e:
            logger.error("Qdrant embedding search failed: %s", e, exc_info=True)
            return []

    # ID: 96844a9d-5c4c-4c98-b245-b329e344973c
    async def get_symbol_embedding(self, symbol_id: str) -> list[float] | None:
        """Get embedding for a symbol by its vector ID."""
        if not self.qdrant:
            return None
        try:
            return await self.qdrant.get_vector_by_id(symbol_id)
        except Exception:
            return None

    # ID: 8ae4adb2-18a5-4f06-a0c9-0e6c5b0996a2
    async def get_neighbors(
        self, symbol_name: str, max_distance: float = 0.5, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get semantic neighbors of a symbol.
        SMART IMPLEMENTATION: Preserved with threshold-aware search.
        """
        if not self.cognitive_service or not self.qdrant:
            return []

        logger.info(
            "Finding semantic neighbors for: %s (radius: %s)", symbol_name, max_distance
        )

        # 1. Generate anchor embedding
        try:
            anchor_vec = await self.cognitive_service.get_embedding_for_code(
                symbol_name
            )
            if not anchor_vec:
                return []
        except Exception as e:
            logger.error("Failed to get anchor embedding: %s", e)
            return []

        # 2. Define similarity threshold (Distance 0.5 = Similarity 0.5)
        min_score = 1.0 - max_distance

        # 3. Perform threshold-aware search
        try:
            results = await self.qdrant.search_similar(
                query_vector=anchor_vec, limit=top_k, with_payload=True
            )

            # 4. Filter by similarity threshold
            items = []
            for hit in results:
                score = hit.get("score", 0.0)
                if score >= min_score:
                    payload = hit.get("payload", {})

                    file_path = payload.get("source_path") or payload.get(
                        "file_path", ""
                    )
                    symbol_path = payload.get("symbol_path") or payload.get(
                        "chunk_id", "unknown"
                    )

                    items.append(
                        {
                            "name": symbol_path,
                            "path": file_path,
                            "item_type": "symbol",
                            "summary": payload.get("content", "")[:200],
                            "score": score,
                            "distance": 1.0 - score,
                            "source": "qdrant",
                        }
                    )

            logger.info(
                "Found %d neighbors within distance %s", len(items), max_distance
            )
            return items

        except Exception as e:
            logger.error("Neighbor search failed: %s", e, exc_info=True)
            return []
