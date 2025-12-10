# src/shared/infrastructure/vector/vector_index_service.py

"""
Unified Vector Indexing Service - Constitutional Infrastructure

Phase 1: Uses QdrantService for upsert operations.
Updated: Implements Smart Deduplication using content hashes.
Fixed: Corrected logging string formatting.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

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


# ID: df12cdd3-8c09-4f51-a453-d5dd6ae03a69
class VectorIndexService:
    """Unified vector indexing service with smart deduplication."""

    def __init__(
        self,
        qdrant_service: QdrantService,
        collection_name: str,
        vector_dim: int | None = None,
    ):
        self.qdrant = qdrant_service
        self.collection_name = collection_name
        self.vector_dim = vector_dim or int(settings.LOCAL_EMBEDDING_DIM)
        self._embedder = build_embedder_from_env()

        logger.info(
            f"VectorIndexService initialized: collection={collection_name}, "
            f"dim={self.vector_dim}"
        )

    # ID: aac3d753-7f8d-44b3-b5a8-2c4da71f8129
    async def ensure_collection(self) -> None:
        """Idempotently create the collection if it doesn't exist."""
        await self.qdrant.ensure_collection(
            collection_name=self.collection_name,
            vector_size=self.vector_dim,
        )

    # ID: 9ec62721-d2ab-47fd-9ae8-f476ae1148fc
    async def index_items(
        self,
        items: list[VectorizableItem],
        batch_size: int = 10,
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

        # --- SMART DEDUPLICATION ---
        # 1. Fetch existing hashes from Qdrant
        stored_hashes = await self.qdrant.get_stored_hashes(self.collection_name)

        items_to_index = []
        skipped_count = 0

        for item in items:
            # Calculate the point ID deterministically using stable hash
            point_id = str(get_deterministic_id(item.item_id))

            new_hash = item.payload.get("content_sha256")

            # If the ID exists and hash matches, skip it
            if (
                point_id in stored_hashes
                and new_hash
                and stored_hashes[point_id] == new_hash
            ):
                skipped_count += 1
                continue

            items_to_index.append(item)

        if skipped_count > 0:
            logger.info(
                f"Skipped {skipped_count} unchanged items (smart deduplication)."
            )

        if not items_to_index:
            logger.info("All items are up to date. Nothing to index.")
            # Return "fake" results for the skipped items so the caller knows they exist
            return [
                IndexResult(
                    item_id=item.item_id,
                    point_id=get_deterministic_id(item.item_id),
                    vector_dim=self.vector_dim,
                )
                for item in items
            ]

        logger.info(
            f"Indexing {len(items_to_index)} new/changed items into {self.collection_name} "
            f"(batch_size={batch_size})"
        )

        results: list[IndexResult] = []

        # Process filtered items in batches
        for i in range(0, len(items_to_index), batch_size):
            batch = items_to_index[i : i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)

            logger.debug(
                f"Processed batch {i // batch_size + 1}/{(len(items_to_index) - 1) // batch_size + 1}"
            )

        logger.info(
            f"✓ Indexed {len(results)}/{len(items_to_index)} items successfully"
        )
        return results

    async def _process_batch(self, items: list[VectorizableItem]) -> list[IndexResult]:
        """Process a single batch: generate embeddings and upsert."""

        # Step 1: Generate embeddings
        embedding_tasks = [self._embedder.get_embedding(item.text) for item in items]
        embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)

        # Step 2: Filter out failed embeddings
        valid_pairs = []
        for item, emb in zip(items, embeddings):
            if isinstance(emb, Exception):
                # FIX: Correct logging format to show item ID and exception message
                logger.warning("Failed to embed %s: %s", item.item_id, emb)
                continue
            if emb is not None:
                valid_pairs.append((item, emb))

        if not valid_pairs:
            return []

        # Step 3: Create Qdrant points
        points = []
        for item, embedding in valid_pairs:
            # Use stable hash
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

        # Step 4: Upsert via Service
        if points:
            await self.qdrant.upsert_points(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

        # Step 5: Build results
        results = [
            IndexResult(
                item_id=item.item_id,
                point_id=get_deterministic_id(item.item_id),
                vector_dim=self.vector_dim,
            )
            for item, _ in valid_pairs
        ]

        return results

    # ID: cb21c047-cfd2-4bef-b81c-17662e402292
    async def query(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: float | None = None,
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
