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


@dataclass
# ID: 37dbacf7-1c1a-4d1d-8e84-f337f1afb4c2
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

    # ID: 0a238825-41b9-4970-8cba-1c1014c9ffb7
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


# ID: 53b6dbe6-aedd-4844-9704-0c6789135cb7
async def get_stored_chunks(qdrant_service: QdrantService) -> dict[str, dict]:
    """
    Return mapping: chunk_id (symbol_key) -> {hash, rev, point_id, capability}

    PHASE 1 FIX: Uses scroll_all_points() service method instead of manual pagination.
    """
    logger.info("Checking Qdrant for already vectorized chunks...")
    chunks: dict[str, dict] = {}
    try:
        stored_points = await qdrant_service.scroll_all_points(
            with_payload=True, with_vectors=False
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
            if len(chunks) >= MAX_SCROLL_LIMIT:
                logger.warning(
                    "Reached MAX_SCROLL_LIMIT of %s chunks, stopping scan",
                    MAX_SCROLL_LIMIT,
                )
                break
        logger.info("Found %s chunks already in Qdrant", len(chunks))
        return chunks
    except Exception as e:
        logger.warning("Could not retrieve stored chunks from Qdrant: %s", e)
        return {}


# ID: b9376676-8bee-4fe6-be8e-3094f8be9877
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


# ID: c6b75e60-f834-4ca1-ade2-c75dae7c4daf
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
        return (False, None)
    try:
        source_code = extract_source_code(repo_root, symbol_data)
        if source_code is None:
            raise ValueError("Source code could not be extracted.")
        payload = _prepare_vectorization_payload(symbol_data, source_code, cap_key)
        if dry_run:
            logger.info("[DRY RUN] Would vectorize '{cap_key}' (chunk: %s)", symbol_key)
            update_data = {"vector_id": f"dry_run_{symbol_key}"}
            return (True, update_data)
        vector = await cognitive_service.get_embedding_for_code(source_code)
        point_id = await qdrant_service.upsert_capability_vector(
            vector=vector, payload_data=payload.to_dict()
        )
        update_data = {
            "vector_id": str(point_id),
            "vectorized_at": datetime.now(UTC).isoformat(),
            "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
            "model_revision": settings.EMBED_MODEL_REVISION,
            "content_hash": payload.content_sha256,
        }
        logger.debug(
            "Successfully vectorized '%s' (chunk: %s) with ID: %s",
            cap_key,
            symbol_key,
            point_id,
        )
        return (True, update_data)
    except Exception as e:
        logger.error("Failed to process capability '{cap_key}': %s", e)
        if not dry_run:
            log_failure(failure_log_path, cap_key, str(e), "knowledge_vectorize")
        if verbose:
            logger.exception("Detailed error for '%s':", cap_key)
        return (False, None)
