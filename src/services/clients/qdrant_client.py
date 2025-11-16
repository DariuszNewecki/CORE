# src/services/clients/qdrant_client.py

"""QdrantService - Quality-first vector database operations with schema enforcement.

This service ensures every vector is stored with complete, traceable provenance
using the EmbeddingPayload schema.
"""

from __future__ import annotations

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

# Track configurations we've already logged, to avoid duplicate INFO lines when the
# same QdrantService configuration is constructed multiple times in the same process.
_SEEN_QDRANT_CONFIGS: set[tuple[str, str, int]] = set()


def _uuid5_from_text(text: str) -> str:
    """Deterministic UUID from text using URL namespace for collision avoidance."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text))


# ID: 3e1fe4a8-df09-4c95-a8b4-52f862e11fda
class VectorNotFoundError(RuntimeError):
    """Raised when a requested vector cannot be retrieved from Qdrant."""

    pass


# ID: ad8ec393-f281-4462-a766-d46a59b0d85c
class InvalidPayloadError(ValueError):
    """Raised when embedding payload validation fails."""

    pass


# ID: a1e22945-e73a-4873-bab2-5b3993507dd7
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
            # First time we see this particular config -> log at INFO
            logger.info(
                "QdrantService initialized: url=%s, collection=%s, dim=%s",
                self.url,
                self.collection_name,
                self.vector_size,
            )
            _SEEN_QDRANT_CONFIGS.add(config_key)
        else:
            # Subsequent constructions with the same config are expected in some
            # CLI paths; keep this at DEBUG to avoid noisy duplicate INFO lines.
            logger.debug(
                "QdrantService reused configuration: url=%s, collection=%s, dim=%s",
                self.url,
                self.collection_name,
                self.vector_size,
            )

    # ID: c7ded463-863f-4730-819d-8e3991980462
    async def ensure_collection(self) -> None:
        """Idempotently create collection if missing."""
        try:
            collections_response = await self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]

            if self.collection_name in existing_collections:
                logger.debug("Collection %s already exists", self.collection_name)
                return

            logger.info(
                "Creating Qdrant collection %s (dim=%s, distance=cosine)",
                self.collection_name,
                self.vector_size,
            )
            await self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=qm.VectorParams(
                    size=self.vector_size,
                    distance=qm.Distance.COSINE,
                ),
                on_disk_payload=True,
            )
        except Exception as e:
            logger.error(
                "Failed to ensure Qdrant collection exists: %s", e, exc_info=True
            )
            raise

    # New canonical symbol-aligned method
    # ID: b8393fbc-2ec4-403a-8b57-b3e9209d8bed
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

    # ID: 69cf555d-0149-4616-88e4-821b88c2a87d
    async def upsert_capability_vector(
        self,
        point_id_str: str,
        vector: list[float],
        payload_data: dict[str, Any],
    ) -> str:
        """
        Deprecated alias for upsert_symbol_vector.

        Kept for backward compatibility; prefer upsert_symbol_vector instead.
        """
        logger.debug(
            "upsert_capability_vector is deprecated; use upsert_symbol_vector instead."
        )
        return await self.upsert_symbol_vector(point_id_str, vector, payload_data)

    # ID: a149a699-a66f-4be2-8787-24e7cf6d05bb
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

    # ID: f0c9a635-8a27-4f7c-a05b-465639de440a
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

        # Try direct vector attribute first
        vec = getattr(rec, "vector", None)
        if isinstance(vec, (list, tuple)):
            return [float(v) for v in vec]

        # Try named vectors
        vectors_obj = getattr(rec, "vectors", None)
        if isinstance(vectors_obj, dict) and vectors_obj:
            # Use configured vector name if available
            if self.vector_name and self.vector_name in vectors_obj:
                chosen = vectors_obj[self.vector_name]
            else:
                # Fallback to first available vector
                first_key = sorted(vectors_obj.keys())[0]
                chosen = vectors_obj[first_key]
                if self.vector_name:
                    logger.debug(
                        "Vector name %s not found, using %s instead",
                        self.vector_name,
                        first_key,
                    )

            if isinstance(chosen, (list, tuple)):
                return [float(v) for v in chosen]

        raise VectorNotFoundError(f"No valid vector found for point {point_id}")

    # ID: 272f9fe7-aa22-4ce7-8c74-94de5bec249b
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
