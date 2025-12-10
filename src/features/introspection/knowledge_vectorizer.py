# src/features/introspection/knowledge_vectorizer.py
"""
Handles the vectorization of individual capabilities (per-chunk), including interaction with Qdrant.
Idempotency is enforced at the chunk (symbol_key) level via `chunk_id` stored in the payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text, sha256_hex
from will.orchestration.cognitive_service import CognitiveService

from .knowledge_helpers import extract_source_code, log_failure


logger = getLogger(__name__)
DEFAULT_PAGE_SIZE = 250
MAX_SCROLL_LIMIT = 10000


# NEW: A dataclass for a clear and type-safe payload structure.
@dataclass
# ID: 941e4256-3c4f-465d-b170-85267270be46
class VectorizationPayload:
    """A structured container for data to be upserted to the vector store."""

    source_path: str
    chunk_id: str
    content_sha256: str
    symbol: str
    capability_tags: list[str]
    model_rev: str
    source_type: str = "code"
    language: str = "python"

    # ID: 6f9d1472-6799-41ff-ac84-cd1d14526932
    def to_dict(self) -> dict[str, Any]:
        """Converts the dataclass to a dictionary for Qdrant."""
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "chunk_id": self.chunk_id,
            "content_sha256": self.content_sha256,
            "language": self.language,
            "symbol": self.symbol,
            "capability_tags": self.capability_tags,
            "model_rev": self.model_rev,
        }


# ID: 11f9a30b-f51d-4b32-a8d3-ca32e5cccfb3
async def get_stored_chunks(qdrant_service: QdrantService) -> dict[str, dict]:
    """
    Return mapping: chunk_id (symbol_key) -> {hash, rev, point_id, capability}

    PHASE 1 FIX: Uses scroll_all_points() service method instead of manual pagination.
    """
    logger.info("Checking Qdrant for already vectorized chunks...")
    chunks: dict[str, dict] = {}

    try:
        # PHASE 1: Use service method for complete collection scanning
        stored_points = await qdrant_service.scroll_all_points(
            with_payload=True,
            with_vectors=False,
        )

        for point in stored_points:
            payload = point.payload or {}
            cid = payload.get("chunk_id")
            if not cid:
                continue
            chunks[cid] = {
                "hash": payload.get("content_sha256"),
                "rev": payload.get("model_rev"),
                "point_id": str(point.id),
                "capability": (payload.get("capability_tags") or [None])[0],
            }

            # Stop if we hit the safety limit
            if len(chunks) >= MAX_SCROLL_LIMIT:
                logger.warning(
                    f"Reached MAX_SCROLL_LIMIT of {MAX_SCROLL_LIMIT} chunks, "
                    "stopping scan"
                )
                break

        logger.info(f"Found {len(chunks)} chunks already in Qdrant")
        return chunks

    except Exception as e:
        logger.warning("Could not retrieve stored chunks from Qdrant: %s", e)
        return {}


# ID: b210df51-5d88-479c-93c9-94c0c63fa72b
async def sync_existing_vector_ids(
    qdrant_service: QdrantService, symbols_map: dict
) -> int:
    """
    Sync vector IDs from Qdrant for chunks (symbols) that already exist
    but don't have vector_id in knowledge graph.
    """
    logger.info("Syncing existing vector IDs from Qdrant...")
    try:
        stored_chunks = await get_stored_chunks(qdrant_service)
        synced_count = 0
        for symbol_key, symbol_data in symbols_map.items():
            if not symbol_data.get("vector_id") and symbol_key in stored_chunks:
                symbol_data["vector_id"] = stored_chunks[symbol_key]["point_id"]
                synced_count += 1
        if synced_count > 0:
            logger.info("Synced %s existing vector IDs from Qdrant", synced_count)
        return synced_count
    except Exception as e:
        logger.warning("Could not sync existing vector IDs from Qdrant: %s", e)
        return 0


# NEW: A pure function for data preparation. Easy to unit test.
def _prepare_vectorization_payload(
    symbol_data: dict[str, Any], source_code: str, cap_key: str
) -> VectorizationPayload:
    """
    Prepares the structured payload for a symbol without performing any I/O.
    """
    normalized_code = normalize_text(source_code)
    content_hash = sha256_hex(normalized_code)
    symbol_key = symbol_data["key"]

    return VectorizationPayload(
        source_path=symbol_data.get("file", "unknown"),
        chunk_id=symbol_key,
        content_sha256=content_hash,
        symbol=symbol_key,
        capability_tags=[cap_key],
        model_rev=settings.EMBED_MODEL_REVISION,
    )


# REFACTORED: This is now a cleaner orchestrator.
# ID: 4a73d0eb-f4c6-420d-a366-4977ca9f7f27
async def process_vectorization_task(
    task: dict,
    repo_root: Path,
    symbols_map: dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    dry_run: bool,
    failure_log_path: Path,
    verbose: bool,
) -> tuple[bool, dict | None]:
    """
    Process a single vectorization task. It orchestrates data preparation,
    embedding, and upserting. It returns a success flag and the data
    to update the symbol map with.
    """
    cap_key = task["cap_key"]
    symbol_key = task["symbol_key"]
    symbol_data = symbols_map.get(symbol_key)

    if not symbol_data:
        logger.error("Symbol '%s' not found in symbols_map.", symbol_key)
        return False, None

    try:
        source_code = extract_source_code(repo_root, symbol_data)
        if source_code is None:
            raise ValueError("Source code could not be extracted.")

        # Step 1: Prepare payload with pure logic
        payload = _prepare_vectorization_payload(symbol_data, source_code, cap_key)

        if dry_run:
            logger.info("[DRY RUN] Would vectorize '{cap_key}' (chunk: %s)", symbol_key)
            update_data = {"vector_id": f"dry_run_{symbol_key}"}
            return True, update_data

        # Step 2: Perform I/O to get embedding
        vector = await cognitive_service.get_embedding_for_code(source_code)

        # Step 3: Perform I/O to upsert to Qdrant
        point_id = await qdrant_service.upsert_capability_vector(
            vector=vector, payload_data=payload.to_dict()
        )

        # Step 4: Return the data for the caller to apply
        update_data = {
            "vector_id": str(point_id),
            "vectorized_at": datetime.now(UTC).isoformat(),
            "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
            "model_revision": settings.EMBED_MODEL_REVISION,
            "content_hash": payload.content_sha256,
        }
        logger.debug(
            f"Successfully vectorized '{cap_key}' (chunk: {symbol_key}) with ID: {point_id}"
        )
        return True, update_data
    except Exception as e:
        logger.error("Failed to process capability '{cap_key}': %s", e)
        if not dry_run:
            log_failure(failure_log_path, cap_key, str(e), "knowledge_vectorize")
        if verbose:
            logger.exception("Detailed error for '%s':", cap_key)
        return False, None
