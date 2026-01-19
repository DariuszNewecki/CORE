# src/will/tools/anchors/storage.py

"""Refactored logic for src/will/tools/anchors/storage.py."""

from __future__ import annotations

from qdrant_client import models as qm

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger


logger = getLogger(__name__)
ANCHOR_COLLECTION = "core_module_anchors"


# ID: 690b9a92-2b8b-4fa8-97e8-0c6163497dc6
async def ensure_anchor_collection(qdrant: QdrantService):
    """Idempotently create Qdrant collection for module anchors."""
    collections_response = await qdrant.client.get_collections()
    existing = [c.name for c in collections_response.collections]
    if ANCHOR_COLLECTION in existing:
        logger.info("Collection %s already exists", ANCHOR_COLLECTION)
        return

    logger.info("Creating collection: %s", ANCHOR_COLLECTION)
    await qdrant.client.recreate_collection(
        collection_name=ANCHOR_COLLECTION,
        vectors_config=qm.VectorParams(size=768, distance=qm.Distance.COSINE),
        on_disk_payload=True,
    )
    logger.info("✅ Collection %s created", ANCHOR_COLLECTION)
