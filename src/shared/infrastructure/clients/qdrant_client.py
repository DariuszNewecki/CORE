# src/shared/infrastructure/clients/qdrant_client.py

"""QdrantService - Quality-first vector database operations with schema enforcement.

This service ensures every vector is stored with complete, traceable provenance
using the EmbeddingPayload schema.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from shared.config import settings
from shared.models import EmbeddingPayload
from shared.time import now_iso


logger = logging.getLogger(__name__)

# Track configurations we've already logged
_SEEN_QDRANT_CONFIGS: set[tuple[str, str, int]] = set()


def _uuid5_from_text(text: str) -> str:
    """Deterministic UUID from text using URL namespace for collision avoidance."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text))


# ID: 3e0fae9f-2236-4307-9f43-2fe602ae9b36
class VectorNotFoundError(RuntimeError):
    """Raised when a requested vector cannot be retrieved from Qdrant."""

    pass


# ID: fdb86b16-1d2e-40e3-a590-063d4ce005b9
class InvalidPayloadError(ValueError):
    """Raised when embedding payload validation fails."""

    pass


# ID: f989ede8-a90b-4d20-bce7-730ccc0108ee
class QdrantService:
    """Handles all interactions with the Qdrant vector database."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        vector_size: int | None = None,
    ) -> None:
        """Initialize Qdrant client from constitutional settings."""
        self.url = url or settings.QDRANT_URL
        self.api_key = (
            api_key
            if api_key is not None
            else settings.model_extra.get("QDRANT_API_KEY")
        )
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.vector_size = int(vector_size or settings.LOCAL_EMBEDDING_DIM)
        self.vector_name: str | None = settings.model_extra.get("QDRANT_VECTOR_NAME")

        if not self.url:
            raise ValueError("QDRANT_URL is not configured.")

        self.client = AsyncQdrantClient(url=self.url, api_key=self.api_key)

        config_key = (self.url, self.collection_name, self.vector_size)
        if config_key not in _SEEN_QDRANT_CONFIGS:
            logger.info(
                "QdrantService initialized: url=%s, collection=%s, dim=%s",
                self.url,
                self.collection_name,
                self.vector_size,
            )
            _SEEN_QDRANT_CONFIGS.add(config_key)

    # ID: b3049399-2d95-4af2-ae34-c150555595d3
    async def ensure_collection(
        self, collection_name: str | None = None, vector_size: int | None = None
    ) -> None:
        """Idempotently create collection if missing."""
        target_name = collection_name or self.collection_name
        target_size = vector_size or self.vector_size

        try:
            collections_response = await self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]

            if target_name in existing_collections:
                logger.debug("Collection %s already exists", target_name)
                return

            logger.info(
                "Creating Qdrant collection %s (dim=%s, distance=cosine)",
                target_name,
                target_size,
            )
            await self.client.recreate_collection(
                collection_name=target_name,
                vectors_config=qm.VectorParams(
                    size=target_size,
                    distance=qm.Distance.COSINE,
                ),
                on_disk_payload=True,
            )
        except Exception as e:
            logger.error(
                "Failed to ensure Qdrant collection exists: %s", e, exc_info=True
            )
            raise

    # ID: d8089d3c-9110-4759-9a18-8df2fb827e92
    async def upsert_symbol_vector(
        self,
        point_id_str: str,
        vector: list[float],
        payload_data: dict[str, Any],
    ) -> str:
        """
        Validate payload against EmbeddingPayload schema and upsert a symbol vector.

        Returns:
            The point ID string.
        """
        if len(vector) != self.vector_size:
            raise ValueError(
                f"Vector dim {len(vector)} != expected {self.vector_size}",
            )

        try:
            # Enforce provenance metadata
            payload_data["model"] = settings.LOCAL_EMBEDDING_MODEL_NAME
            payload_data["model_rev"] = settings.EMBED_MODEL_REVISION
            payload_data["dim"] = self.vector_size
            payload_data["created_at"] = now_iso()
            payload = EmbeddingPayload(**payload_data)
        except Exception as e:
            logger.error("Invalid embedding payload: %s", e)
            raise InvalidPayloadError(f"Invalid embedding payload: {e}") from e

        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                qm.PointStruct(
                    id=point_id_str,
                    vector=vector,
                    payload=payload.model_dump(mode="json"),
                )
            ],
            wait=True,
        )
        logger.debug(
            "Upserted vector for chunk %s with ID: %s",
            payload.chunk_id,
            point_id_str,
        )
        return point_id_str

    # ID: 98614945-4d37-4cff-9977-bd59ae8c550d
    async def upsert_capability_vector(
        self,
        point_id_str: str,
        vector: list[float],
        payload_data: dict[str, Any],
    ) -> str:
        """
        Deprecated alias for upsert_symbol_vector.
        Kept for backward compatibility.
        """
        logger.debug(
            "upsert_capability_vector is deprecated; use upsert_symbol_vector instead."
        )
        return await self.upsert_symbol_vector(point_id_str, vector, payload_data)

    # ID: 4a4561cb-79aa-4aa2-bc77-d259999e3e18
    async def get_all_vectors(self) -> list[qm.Record]:
        """Fetch all points with vectors and payloads from the collection."""
        try:
            records, _ = await self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=True,
            )
            logger.debug(
                "Retrieved %s vectors from collection %s",
                len(records),
                self.collection_name,
            )
            return records
        except Exception as e:
            logger.error("Failed to retrieve all vectors: %s", e)
            return []

    # ID: 7f84df15-9515-4631-93c6-9700b2e578f6
    async def get_vector_by_id(self, point_id: str) -> list[float]:
        """
        Retrieve a single vector by its point ID.

        Raises:
            VectorNotFoundError: If the vector cannot be found or retrieved.
        """
        try:
            records = await self.client.retrieve(
                collection_name=self.collection_name,
                ids=[str(point_id)],
                with_vectors=True,
                with_payload=False,
            )
        except Exception as e:
            logger.warning("Failed to retrieve vector %s: %s", point_id, e)
            raise VectorNotFoundError(f"Failed to retrieve vector {point_id}") from e

        if not records:
            raise VectorNotFoundError(f"Vector not found for point {point_id}")

        rec = records[0]
        # Robust vector extraction
        vec = getattr(rec, "vector", None)
        if isinstance(vec, (list, tuple)):
            return [float(v) for v in vec]

        # Check named vectors if needed
        vectors_obj = getattr(rec, "vectors", None)
        if isinstance(vectors_obj, dict) and vectors_obj:
            first_key = sorted(vectors_obj.keys())[0]
            chosen = vectors_obj.get(self.vector_name) or vectors_obj[first_key]
            if isinstance(chosen, (list, tuple)):
                return [float(v) for v in chosen]

        # Fallback dictionary access
        try:
            rec_dict = dict(rec)
            vec_from_dict = rec_dict.get("vector")
            if isinstance(vec_from_dict, (list, tuple)):
                return [float(v) for v in vec_from_dict]
        except Exception:
            pass

        raise VectorNotFoundError(f"No valid vector found for point {point_id}")

    # ID: c1fdf49b-a4f3-4e5f-9f63-2c1a05b6a33c
    async def search_similar(
        self,
        query_vector: Sequence[float],
        limit: int = 5,
        with_payload: bool = True,
        filter_: qm.Filter | None = None,
    ) -> list[dict[str, Any]]:
        """Perform similarity search for the given query vector."""
        try:
            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=[float(v) for v in query_vector],
                limit=limit,
                with_payload=with_payload,
                query_filter=filter_,
            )
            return [
                {"score": hit.score, "payload": hit.payload} for hit in search_result
            ]
        except Exception as e:
            logger.error(
                "Similarity search failed in %s: %s",
                self.collection_name,
                e,
            )
            return []

    # ========================================================================
    # NEW HELPER METHODS FOR VECTOR SERVICE STANDARDIZATION
    # ========================================================================

    # ID: 6e07e45f-5abc-40ac-8a0a-68c2d6a85bf8
    async def upsert_points(
        self, collection_name: str, points: list[qm.PointStruct], wait: bool = True
    ) -> None:
        """
        Generic safe upsert for points.
        Used by pattern and policy vectorizers to insert into specific collections.
        """
        try:
            await self.client.upsert(
                collection_name=collection_name, points=points, wait=wait
            )
        except Exception as e:
            logger.error("Failed to upsert points to {collection_name}: %s", e)
            raise

    # ID: bc27e697-1f06-4afe-bdb0-1edbfa248b71
    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        query_filter: qm.Filter | None = None,
        score_threshold: float | None = None,
    ) -> list[qm.ScoredPoint]:
        """
        Generic safe search wrapper.
        Used by pattern and policy vectorizers to search specific collections.
        """
        try:
            return await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
            )
        except Exception as e:
            logger.error("Search failed in {collection_name}: %s", e)
            raise

    # ID: 65a738fe-3ed6-49e3-8377-c529d33447d9
    async def scroll_all_points(
        self,
        with_payload: bool = True,
        with_vectors: bool = False,
        page_size: int = 10_000,
        collection_name: str | None = None,
    ) -> list[qm.Record]:
        """
        Scroll through ALL points in the collection with proper pagination.
        Handles pagination automatically and returns all points.
        """
        target_collection = collection_name or self.collection_name
        all_points: list[qm.Record] = []
        offset: str | None = None

        while True:
            try:
                points, offset = await self.client.scroll(
                    collection_name=target_collection,
                    limit=page_size,
                    offset=offset,
                    with_payload=with_payload,
                    with_vectors=with_vectors,
                )

                if not points:
                    break

                all_points.extend(points)

                if offset is None:
                    break

            except Exception as e:
                logger.error(
                    "Failed to scroll collection %s at offset %s: %s",
                    target_collection,
                    offset,
                    e,
                )
                raise

        return all_points

    # ID: 51ea2c61-7b6f-4f6a-94d3-ea7ac08e130f
    async def delete_points(
        self,
        point_ids: list[str],
        wait: bool = True,
        collection_name: str | None = None,
    ) -> int:
        """
        Delete multiple points by ID with validation and logging.
        """
        target_collection = collection_name or self.collection_name

        if not point_ids:
            return 0

        try:
            logger.info(
                "Deleting %d points from %s",
                len(point_ids),
                target_collection,
            )

            await self.client.delete(
                collection_name=target_collection,
                points_selector=qm.PointIdsList(points=point_ids),
                wait=wait,
            )

            return len(point_ids)

        except Exception as e:
            logger.error(
                "Failed to delete points from %s: %s",
                target_collection,
                e,
            )
            raise

    # ID: 86b61a51-a4af-40f4-af4b-a788019d1eb1
    async def get_stored_hashes(
        self, collection_name: str | None = None
    ) -> dict[str, str]:
        """
        Retrieve all point IDs and their content_sha256 hashes.
        Enables hash-based deduplication to check if content has changed.
        """
        target_collection = collection_name or self.collection_name
        logger.debug("Fetching stored hashes from %s", target_collection)

        hashes: dict[str, str] = {}
        offset: str | None = None

        while True:
            try:
                points, offset = await self.client.scroll(
                    collection_name=target_collection,
                    limit=10_000,
                    offset=offset,
                    with_payload=["content_sha256"],
                    with_vectors=False,
                )

                for point in points:
                    if point.payload and "content_sha256" in point.payload:
                        hashes[str(point.id)] = point.payload["content_sha256"]

                if offset is None:
                    break

            except Exception as e:
                logger.warning(
                    "Could not retrieve hashes from %s: %s",
                    target_collection,
                    e,
                )
                # Return partial results rather than failing completely
                break

        return hashes
