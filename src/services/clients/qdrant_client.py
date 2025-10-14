# src/services/clients/qdrant_client.py
"""
QdrantService (quality-first, single-file)

This service now enforces the EmbeddingPayload schema for all upserts,
ensuring every vector is stored with complete, traceable provenance.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from shared.config import settings
from shared.models import EmbeddingPayload
from shared.time import now_iso as _now_iso

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models as qm
except Exception as e:
    raise RuntimeError(
        "qdrant-client is required. Install with: pip install qdrant-client"
    ) from e

try:
    from shared.logger import getLogger

    log = getLogger("qdrant_service")
except Exception:
    import logging

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("qdrant_service")


def _uuid5_from_text(text: str) -> str:
    """
    Deterministic UUID from text (stable across runs).
    Uses UUID5 with URL namespace to avoid collisions.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text))


# ID: 53349105-1b11-4917-9e24-ce9dc6f9a128
class QdrantService:
    """Handles all interactions with the Qdrant vector database."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        vector_size: int | None = None,
    ) -> None:
        """Initializes the Qdrant client from constitutional settings."""
        self.url = url or settings.QDRANT_URL
        self.api_key = (
            api_key
            if api_key is not None
            else settings.model_extra.get("QDRANT_API_KEY")
        )
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.vector_size = int(vector_size or settings.LOCAL_EMBEDDING_DIM)

        # Optional support for named vectors if your collection is later migrated.
        # If set, we'll prefer this key inside record.vectors.
        self.vector_name: str | None = settings.model_extra.get("QDRANT_VECTOR_NAME")

        if not self.url:
            raise ValueError("QDRANT_URL is not configured.")

        self.client = AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key or None,
        )

        log.info(
            "QdrantService: url=%s collection=%s dim=%s",
            self.url,
            self.collection_name,
            self.vector_size,
        )

    # ID: 299a4be1-32fe-4c3f-aad4-f8d15065111e
    async def ensure_collection(self) -> None:
        """Idempotently create the collection if it is missing."""
        try:
            collections_response = await self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]
            if self.collection_name in existing_collections:
                return

            log.info(
                "Creating Qdrant collection '%s' (dim=%s, distance=cosine).",
                self.collection_name,
                self.vector_size,
            )

            await self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=qm.VectorParams(
                    size=self.vector_size, distance=qm.Distance.COSINE
                ),
                on_disk_payload=True,
            )
        except Exception as e:
            log.error(f"Failed to ensure Qdrant collection exists: {e}", exc_info=True)
            raise

    # ID: 1aa3971e-527b-481a-8029-c8ad01b5e670
    async def upsert_capability_vector(
        self,
        point_id_str: str,
        vector: list[float],
        payload_data: dict,
    ) -> str:
        """
        Validates the payload against the EmbeddingPayload schema and upserts the vector.
        Uses the provided point ID. Returns the point ID.
        """
        if len(vector) != self.vector_size:
            raise ValueError(f"Vector dim {len(vector)} != expected {self.vector_size}")

        try:
            payload_data["model"] = settings.LOCAL_EMBEDDING_MODEL_NAME
            payload_data["model_rev"] = settings.EMBED_MODEL_REVISION
            payload_data["dim"] = self.vector_size
            payload_data["created_at"] = _now_iso()
            payload = EmbeddingPayload(**payload_data)
        except Exception as e:
            log.error(f"Invalid embedding payload: {e}")
            raise ValueError(f"Invalid embedding payload: {e}") from e

        pid = point_id_str

        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                qm.PointStruct(
                    id=pid,
                    vector=vector,
                    payload=payload.model_dump(mode="json"),
                )
            ],
            wait=True,
        )

        log.debug(f"Upserted vector for chunk '{payload.chunk_id}' with ID: {pid}")
        return pid

    # ID: 400e23e3-0911-4419-86be-9b06ba5b3fb5
    async def get_all_vectors(self) -> list[qm.Record]:
        """Fetches all points with their vectors and payloads from the collection."""
        try:
            records, _ = await self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=True,
            )
            return records
        except Exception as e:
            log.error(f"❌ Failed to retrieve all vectors from Qdrant: {e}")
            return []

    # ID: 19e184b6-3b4e-483f-902d-c8ac35d3e8d4 (updated)
    async def get_vector_by_id(self, point_id: str) -> list[float] | None:
        """
        Retrieves a single vector by its point ID.
        """
        try:
            records = await self.client.retrieve(
                collection_name=self.collection_name,
                ids=[str(point_id)],  # ensure it's a string
                with_vectors=True,
                with_payload=False,
            )
        # --- THIS IS THE DIAGNOSTIC FIX ---
        except Exception as e:
            # This new, more specific logging will tell us the real error.
            log.warning(
                "Could not retrieve vector for point ID %s (collection=%s): An unexpected exception occurred during the API call. Type: %s, Error: %s",
                point_id,
                self.collection_name,
                type(e).__name__,
                e,
            )
            return None
        # --- END OF FIX ---

        if not records:
            log.warning(
                "Could not retrieve vector for point ID %s (collection=%s): point not found",
                point_id,
                self.collection_name,
            )
            return None

        rec = records[0]

        # Case 1: classic single vector
        vec = getattr(rec, "vector", None)
        if isinstance(vec, (list, tuple)):
            return list(map(float, vec))

        # Case 2: newer clients / named vectors
        vectors_obj = getattr(rec, "vectors", None)
        if isinstance(vectors_obj, dict):
            # Prefer configured name if provided
            if self.vector_name and self.vector_name in vectors_obj:
                chosen = vectors_obj[self.vector_name]
                if isinstance(chosen, (list, tuple)):
                    return list(map(float, chosen))

            # Fallback: pick first key deterministically
            if vectors_obj:
                first_key = sorted(vectors_obj.keys())[0]
                chosen = vectors_obj[first_key]
                if isinstance(chosen, (list, tuple)):
                    log.debug(
                        "Using named vector '%s' for point %s (collection=%s) "
                        "because QDRANT_VECTOR_NAME is not set.",
                        first_key,
                        point_id,
                        self.collection_name,
                    )
                    return list(map(float, chosen))

            log.warning(
                "Could not retrieve vector for point ID %s (collection=%s): vectors dict present but empty or invalid. keys=%s",
                point_id,
                self.collection_name,
                list(vectors_obj.keys()) if isinstance(vectors_obj, dict) else None,
            )
            return None

        log.warning(
            "Could not retrieve vector for point ID %s (collection=%s): "
            "no usable 'vector' or 'vectors' on record. attrs(vector=%s, vectors_type=%s)",
            point_id,
            self.collection_name,
            type(getattr(rec, "vector", None)).__name__,
            type(getattr(rec, "vectors", None)).__name__,
        )
        return None

    # (unchanged) simple search helper
    # ID: b969f68c-ab5b-473b-8a9c-c53cffd38199
    async def search_similar(
        self,
        query_vector: Sequence[float],
        limit: int = 5,
        with_payload: bool = True,
        filter_: qm.Filter | None = None,
    ) -> list[dict[str, Any]]:
        """
        Simple nearest-neighbor search.
        """
        search_result = await self.client.search(
            collection_name=self.collection_name,
            query_vector=list(map(float, query_vector)),
            limit=limit,
            with_payload=with_payload,
            query_filter=filter_,
        )
        return [{"score": hit.score, "payload": hit.payload} for hit in search_result]
