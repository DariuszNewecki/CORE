# src/shared/infrastructure/vector/vector_index_service.py

"""
Unified Vector Indexing Service - Constitutional Infrastructure

- Uses QdrantService for upsert operations.
- Implements Smart Deduplication using content hashes.
- Embeddings are obtained via an injected Embeddable provider.
  Default provider is the local-only embedder from shared.utils.embedding_utils.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models.vector_models import IndexResult, VectorizableItem
from shared.universal import get_deterministic_id
from shared.utils.embedding_utils import Embeddable, build_embedder_from_env


if TYPE_CHECKING:
    pass

logger = getLogger(__name__)


# ID: 2ffe6361-bae9-4b98-936c-95cfe52a1d8b
class VectorIndexService:
    """
    Unified vector indexing service with smart deduplication.

    Constitutional embedding rule:
    - VectorIndexService does not implement embedding logic.
    - It consumes an Embeddable provider (injected), or falls back to the
      local-only embedder factory (settings-based, no env access).
    """

    def __init__(
        self,
        qdrant_service: QdrantService,
        collection_name: str,
        vector_dim: int | None = None,
        embedder: Embeddable | None = None,
    ) -> None:
        self.qdrant = qdrant_service
        self.collection_name = collection_name
        self.vector_dim = vector_dim or int(settings.LOCAL_EMBEDDING_DIM)

        self._embedder: Embeddable = embedder or build_embedder_from_env()

        logger.info(
            "VectorIndexService initialized: collection=%s dim=%s embedder=%s",
            self.collection_name,
            self.vector_dim,
            type(self._embedder).__name__,
        )

    # ID: 016343de-1f7d-4b55-bc00-ee7cc2565175
    async def ensure_collection(self) -> None:
        await self.qdrant.ensure_collection(
            collection_name=self.collection_name,
            vector_size=self.vector_dim,
        )

    # ID: 14aa6d5e-820b-4b0b-b77a-6da102e780ed
    async def index_items(
        self,
        items: list[VectorizableItem],
        batch_size: int = 10,
    ) -> list[IndexResult]:
        if not items:
            raise ValueError("Cannot index empty list of items")

        stored_hashes = await self.qdrant.get_stored_hashes(self.collection_name)
        items_to_index: list[VectorizableItem] = []
        skipped_count = 0

        for item in items:
            point_id = str(get_deterministic_id(item.item_id))
            new_hash = item.payload.get("content_sha256")

            if (
                point_id in stored_hashes
                and new_hash
                and stored_hashes[point_id] == new_hash
            ):
                skipped_count += 1
                continue

            items_to_index.append(item)

        if skipped_count:
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
            results.extend(await self._process_batch(batch))
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
        tasks = [self._embedder.get_embedding(item.text) for item in items]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        valid_pairs: list[tuple[VectorizableItem, list[float]]] = []

        for item, emb in zip(items, embeddings):
            if isinstance(emb, Exception):
                logger.warning("Failed to embed %s: %s", item.item_id, emb)
                continue
            if not emb:
                logger.warning("Failed to embed %s: empty embedding", item.item_id)
                continue

            vector = list(emb)

            # Constitutional invariant: vector dim must match collection dim
            if len(vector) != self.vector_dim:
                logger.error(
                    "Embedding dimension mismatch for %s: got=%s expected=%s",
                    item.item_id,
                    len(vector),
                    self.vector_dim,
                )
                continue

            valid_pairs.append((item, vector))

        if not valid_pairs:
            return []

        bulk_items: list[tuple[str, list[float], dict]] = []
        for item, vector in valid_pairs:
            point_id_str = str(get_deterministic_id(item.item_id))
            payload = {
                **item.payload,
                "item_id": item.item_id,
                "chunk_id": item.item_id,
            }

            if "source_path" not in payload:
                payload["source_path"] = payload.get(
                    "file_path", f".intent/{item.item_id.split(':')[0]}.json"
                )
            if "source_type" not in payload:
                payload["source_type"] = payload.get("doc_type", "intent")

            bulk_items.append((point_id_str, vector, payload))

        await self.qdrant.upsert_symbol_vectors_bulk(
            bulk_items,
            collection_name=self.collection_name,
            wait=True,
        )

        return [
            IndexResult(
                item_id=item.item_id,
                point_id=get_deterministic_id(item.item_id),
                vector_dim=self.vector_dim,
            )
            for item, _vector in valid_pairs
        ]

    # ID: a74ccda4-917d-4da6-b172-e807c7e8d16f
    async def query(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: float | None = None,
    ) -> list[dict]:
        vec = await self._embedder.get_embedding(query_text)
        if not vec:
            logger.warning("Failed to generate query embedding")
            return []

        query_vector = list(vec)

        if len(query_vector) != self.vector_dim:
            logger.error(
                "Query embedding dimension mismatch: got=%s expected=%s",
                len(query_vector),
                self.vector_dim,
            )
            return []

        results = await self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [{"score": hit.score, "payload": hit.payload} for hit in results]
