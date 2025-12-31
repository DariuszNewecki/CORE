# src/shared/infrastructure/vector/vector_index_service.py

"""
Unified Vector Indexing Service - Constitutional Infrastructure

Phase 1: Uses QdrantService for upsert operations.
Updated: Implements Smart Deduplication using content hashes.
Enhanced: Supports injectable embedder for flexibility.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from qdrant_client.http import models as qm

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models.vector_models import IndexResult, VectorizableItem
from shared.universal import get_deterministic_id
from shared.utils.embedding_utils import build_embedder_from_env


if TYPE_CHECKING:
    pass

logger = getLogger(__name__)


# ID: embeddable_protocol
# ID: c754f237-05e1-4d8d-90a2-c688832185c6
class Embeddable(Protocol):
    """Protocol for any service that can generate embeddings."""

    # ID: 5fd49aab-51aa-447b-9901-54579a9d97d6
    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        ...


# ID: 5964433e-d92a-4d2e-936b-4385d0e6c37c
class VectorIndexService:
    """
    Unified vector indexing service with smart deduplication.

    Supports both local embeddings and CognitiveService via dependency injection.
    """

    def __init__(
        self,
        qdrant_service: QdrantService,
        collection_name: str,
        vector_dim: int | None = None,
        embedder: Embeddable | None = None,
    ):
        """
        Initialize VectorIndexService.

        Args:
            qdrant_service: Qdrant client service
            collection_name: Target collection name
            vector_dim: Vector dimension (defaults to LOCAL_EMBEDDING_DIM)
            embedder: Optional custom embedder (defaults to build_embedder_from_env)
                     Use this to inject CognitiveService or other embedding providers
        """
        self.qdrant = qdrant_service
        self.collection_name = collection_name
        self.vector_dim = vector_dim or int(settings.LOCAL_EMBEDDING_DIM)

        # ENHANCED: Embedder is now injectable!
        if embedder is not None:
            self._embedder = embedder
            logger.info(
                "VectorIndexService initialized with custom embedder: collection=%s, dim=%s",
                collection_name,
                self.vector_dim,
            )
        else:
            self._embedder = build_embedder_from_env()
            logger.info(
                "VectorIndexService initialized with default embedder: collection=%s, dim=%s",
                collection_name,
                self.vector_dim,
            )

    # ID: c988ed56-fc8d-42d9-bb8d-22d4c8ff31ea
    async def ensure_collection(self) -> None:
        """Idempotently create the collection if it doesn't exist."""
        await self.qdrant.ensure_collection(
            collection_name=self.collection_name, vector_size=self.vector_dim
        )

    # ID: 362c6f11-eda1-47ab-a3f6-8d8b48261519
    async def index_items(
        self, items: list[VectorizableItem], batch_size: int = 10
    ) -> list[IndexResult]:
        """
        Index a batch of items: generate embeddings and upsert to Qdrant.
        Skips items that are already indexed with the same content hash.

        Args:
            items: List of VectorizableItem objects to index
            batch_size: Number of items to process in parallel

        Returns:
            List of IndexResult objects with point IDs
        """
        if not items:
            raise ValueError("Cannot index empty list of items")

        # SMART DEDUPLICATION: Check existing hashes
        stored_hashes = await self.qdrant.get_stored_hashes(self.collection_name)
        items_to_index = []
        skipped_count = 0

        for item in items:
            point_id = str(get_deterministic_id(item.item_id))
            new_hash = item.payload.get("content_sha256")

            # Skip if hash matches (content unchanged)
            if (
                point_id in stored_hashes
                and new_hash
                and (stored_hashes[point_id] == new_hash)
            ):
                skipped_count += 1
                continue

            items_to_index.append(item)

        if skipped_count > 0:
            logger.info(
                "Skipped %s unchanged items (smart deduplication).", skipped_count
            )

        if not items_to_index:
            logger.info("All items are up to date. Nothing to index.")
            return [
                IndexResult(
                    item_id=item.item_id,
                    point_id=get_deterministic_id(item.item_id),
                    vector_dim=self.vector_dim,
                )
                for item in items
            ]

        logger.info(
            "Indexing %s new/changed items into %s (batch_size=%s)",
            len(items_to_index),
            self.collection_name,
            batch_size,
        )

        results: list[IndexResult] = []
        for i in range(0, len(items_to_index), batch_size):
            batch = items_to_index[i : i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)
            logger.debug(
                "Processed batch %s/%s",
                i // batch_size + 1,
                (len(items_to_index) - 1) // batch_size + 1,
            )

        logger.info(
            "✓ Indexed %s/%s items successfully", len(results), len(items_to_index)
        )
        return results

    async def _process_batch(self, items: list[VectorizableItem]) -> list[IndexResult]:
        """Process a single batch: generate embeddings and upsert."""
        # Generate embeddings in parallel
        embedding_tasks = [self._embedder.get_embedding(item.text) for item in items]
        embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)

        # Filter out failures
        valid_pairs = []
        for item, emb in zip(items, embeddings):
            if isinstance(emb, Exception):
                logger.warning("Failed to embed %s: %s", item.item_id, emb)
                continue
            if emb is not None:
                valid_pairs.append((item, emb))

        if not valid_pairs:
            return []

        # Build points for Qdrant
        points = []
        for item, embedding in valid_pairs:
            point_id = get_deterministic_id(item.item_id)
            payload = {
                **item.payload,
                "item_id": item.item_id,
                "model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                "model_rev": settings.EMBED_MODEL_REVISION,
                "dim": self.vector_dim,
            }
            points.append(
                qm.PointStruct(
                    id=point_id,
                    vector=(
                        embedding.tolist()
                        if hasattr(embedding, "tolist")
                        else list(embedding)
                    ),
                    payload=payload,
                )
            )

        # Upsert to Qdrant
        if points:
            await self.qdrant.upsert_points(
                collection_name=self.collection_name, points=points, wait=True
            )

        # Return results
        results = [
            IndexResult(
                item_id=item.item_id,
                point_id=get_deterministic_id(item.item_id),
                vector_dim=self.vector_dim,
            )
            for item, _ in valid_pairs
        ]
        return results

    # ID: 2544b299-de9a-4e8f-86d7-f21ff614f979
    async def query(
        self, query_text: str, limit: int = 5, score_threshold: float | None = None
    ) -> list[dict]:
        """Semantic search in the collection."""
        query_vector = await self._embedder.get_embedding(query_text)
        if query_vector is None:
            logger.warning("Failed to generate query embedding")
            return []

        if hasattr(query_vector, "tolist"):
            query_vector = query_vector.tolist()

        results = await self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [{"score": hit.score, "payload": hit.payload} for hit in results]
