# src/services/vector/vector_index_service.py
"""
Unified Vector Indexing Service - Constitutional Infrastructure

Fixed: Runtime import of IndexResult.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from qdrant_client.models import Distance, PointStruct, VectorParams
from shared.config import settings
from shared.logger import getLogger

# FIX: Import models at runtime
from shared.models.vector_models import IndexResult, VectorizableItem
from shared.utils.embedding_utils import build_embedder_from_env

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient

logger = getLogger(__name__)


# ID: 71d4ffa4-e0a5-4c7d-a4bd-f530a76605a4
class VectorIndexService:
    # ... (rest of class remains identical) ...
    # Just ensure the import above is fixed.

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        collection_name: str,
        vector_dim: int | None = None,
    ):
        """
        Initialize the vector indexing service.

        Args:
            qdrant_client: Async Qdrant client instance
            collection_name: Name of the target collection
            vector_dim: Vector dimension (defaults to LOCAL_EMBEDDING_DIM)
        """
        self.client = qdrant_client
        self.collection_name = collection_name
        self.vector_dim = vector_dim or int(settings.LOCAL_EMBEDDING_DIM)

        # Use CORE's existing embedding infrastructure
        self._embedder = build_embedder_from_env()

        logger.info(
            f"VectorIndexService initialized: collection={collection_name}, "
            f"dim={self.vector_dim}"
        )

    # ID: cff34c47-fca3-4241-b062-e0dbbeae110c
    async def ensure_collection(self) -> None:
        """
        Idempotently create the collection if it doesn't exist.

        Uses correct dimensions from configuration.
        Safe to call multiple times.
        """
        collections_response = await self.client.get_collections()
        existing = {c.name for c in collections_response.collections}

        if self.collection_name in existing:
            logger.debug(f"Collection {self.collection_name} already exists")
            return

        logger.info(
            f"Creating collection: {self.collection_name} "
            f"(dim={self.vector_dim}, distance=cosine)"
        )

        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_dim,
                distance=Distance.COSINE,
            ),
        )

        logger.info(f"✓ Created collection: {self.collection_name}")

    # ID: f95ced0c-30a9-42a6-a18b-ea0c01b2afc0
    async def index_items(
        self,
        items: list[VectorizableItem],
        batch_size: int = 10,
    ) -> list[IndexResult]:
        """
        Index a batch of items: generate embeddings and upsert to Qdrant.

        This is the CORE operation that all vectorization flows through.

        Args:
            items: List of VectorizableItem objects to index
            batch_size: Number of items to process in parallel

        Returns:
            List of IndexResult objects with point IDs

        Raises:
            ValueError: If items list is empty
            RuntimeError: If embedding generation fails for all items
        """
        if not items:
            raise ValueError("Cannot index empty list of items")

        logger.info(
            f"Indexing {len(items)} items into {self.collection_name} "
            f"(batch_size={batch_size})"
        )

        results: list[IndexResult] = []

        # Process in batches to avoid overwhelming the embedding service
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)

            logger.debug(
                f"Processed batch {i // batch_size + 1}/{(len(items) - 1) // batch_size + 1}"
            )

        logger.info(f"✓ Indexed {len(results)}/{len(items)} items successfully")
        return results

    async def _process_batch(self, items: list[VectorizableItem]) -> list[IndexResult]:
        """
        Process a single batch: generate embeddings and upsert.

        Args:
            items: Batch of items to process

        Returns:
            List of IndexResult for successfully indexed items
        """
        # Step 1: Generate embeddings using CORE's embedding service
        embedding_tasks = [self._embedder.get_embedding(item.text) for item in items]
        embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)

        # Step 2: Filter out failed embeddings
        valid_pairs = []
        for item, emb in zip(items, embeddings):
            if isinstance(emb, Exception):
                logger.warning(f"Failed to embed {item.item_id}: {emb}")
                continue
            if emb is not None:
                valid_pairs.append((item, emb))

        if not valid_pairs:
            logger.warning("All embeddings failed in batch")
            return []

        # Step 3: Create Qdrant points
        points = []
        for item, embedding in valid_pairs:
            point_id = hash(item.item_id) % (2**63)  # Convert to positive int64

            # Enrich payload with metadata
            payload = {
                **item.payload,
                "item_id": item.item_id,
                "model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                "model_rev": settings.EMBED_MODEL_REVISION,
                "dim": self.vector_dim,
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=(
                        embedding.tolist()
                        if hasattr(embedding, "tolist")
                        else list(embedding)
                    ),
                    payload=payload,
                )
            )

        # Step 4: Upsert to Qdrant
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

        # Step 5: Build results
        # FIX: IndexResult is now imported at runtime
        results = [
            IndexResult(
                item_id=item.item_id,
                point_id=hash(item.item_id) % (2**63),
                vector_dim=self.vector_dim,
            )
            for item, _ in valid_pairs
        ]

        return results

    # ID: 359b81c9-a347-4e3c-96d7-abf833afb1fa
    async def query(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """
        Semantic search in the collection.

        Args:
            query_text: Natural language query
            limit: Maximum results to return
            score_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of dicts with 'score' and 'payload' keys
        """
        # Generate query embedding using CORE's embedding service
        query_vector = await self._embedder.get_embedding(query_text)

        if query_vector is None:
            logger.warning("Failed to generate query embedding")
            return []

        # Convert to list if numpy array
        if hasattr(query_vector, "tolist"):
            query_vector = query_vector.tolist()

        # Search Qdrant
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [{"score": hit.score, "payload": hit.payload} for hit in results]
