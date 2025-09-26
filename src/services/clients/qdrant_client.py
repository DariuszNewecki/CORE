# src/services/clients/qdrant_client.py
"""
QdrantService (quality-first, single-file)

This service now enforces the EmbeddingPayload schema for all upserts,
ensuring every vector is stored with complete, traceable provenance.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional, Sequence

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


# ID: 3f5ec13f-ba90-4912-99fb-a040ac649db8
class QdrantService:
    """Handles all interactions with the Qdrant vector database."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
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

    # ID: 5f745907-7aab-4426-a8ed-573607f3e6d4
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

    # ID: 21ca9b0a-5f75-4707-bd86-c2289d954b25
    async def upsert_capability_vector(
        self,
        vector: List[float],
        payload_data: dict,
    ) -> str:
        """
        Validates the payload against the EmbeddingPayload schema and upserts the vector.
        Deterministic ID derived from the chunk_id. Returns the point ID.
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

        pid = _uuid5_from_text(payload.chunk_id)

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

        log.info(f"Upserted vector for chunk '{payload.chunk_id}' with ID: {pid}")
        return pid

    # ID: fba683c2-34d0-4feb-96ab-950c97abbb49
    async def get_all_vectors(self) -> List[qm.Record]:
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

    # ID: 0e8ad7db-3561-4f97-9891-ca419e374dcf
    async def search_similar(
        self,
        query_vector: Sequence[float],
        limit: int = 5,
        with_payload: bool = True,
        filter_: Optional[qm.Filter] = None,
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

    # ID: 55effb86-fea5-4dc8-bdce-e9b464e9f243
    async def get_vector_by_id(self, point_id: str) -> Optional[List[float]]:
        """Retrieves a single vector by its point ID."""
        try:
            records = await self.client.retrieve(
                collection_name=self.collection_name, ids=[point_id], with_vectors=True
            )
            if records and records[0].vector:
                return records[0].vector
        except Exception as e:
            log.warning(f"Could not retrieve vector for point ID {point_id}: {e}")
        return None
