# src/system/admin/knowledge_vectorizer.py
"""
Handles the vectorization of individual capabilities (per-chunk), including interaction with Qdrant.
Idempotency is enforced at the chunk (symbol_key) level via `chunk_id` stored in the payload.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.cognitive_service import CognitiveService
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.logger import getLogger
from shared.services.embedding_utils import normalize_text, sha256_hex

from .knowledge_helpers import extract_source_code, log_failure

log = getLogger("core_admin.knowledge")

DEFAULT_PAGE_SIZE = 250
MAX_SCROLL_LIMIT = 10000


# ID: 81ddb9e8-60c9-4564-bd08-b5e6c2843381
async def get_stored_chunks(qdrant_service: QdrantService) -> dict[str, dict]:
    """
    Return mapping: chunk_id (symbol_key) -> {hash, rev, point_id, capability}
    """
    log.info("Checking Qdrant for already vectorized chunks...")
    chunks: dict[str, dict] = {}
    next_offset = None
    try:
        while True:
            stored_points, next_offset = await qdrant_service.client.scroll(
                collection_name=qdrant_service.collection_name,
                limit=DEFAULT_PAGE_SIZE,
                offset=next_offset,
                with_payload=[
                    "chunk_id",
                    "content_sha256",
                    "model_rev",
                    "capability_tags",
                ],
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
            if not next_offset:
                break
        log.info(f"Found {len(chunks)} chunks already in Qdrant")
        return chunks
    except Exception as e:
        log.warning(f"Could not retrieve stored chunks from Qdrant: {e}")
        return {}


# ID: 9e54c111-0ffc-4a99-b243-8b89569335e1
async def sync_existing_vector_ids(
    qdrant_service: QdrantService, symbols_map: dict
) -> int:
    """
    Sync vector IDs from Qdrant for chunks (symbols) that already exist
    but don't have vector_id in knowledge graph.
    """
    log.info("Syncing existing vector IDs from Qdrant...")
    try:
        stored_points, _ = await qdrant_service.client.scroll(
            collection_name=qdrant_service.collection_name,
            limit=MAX_SCROLL_LIMIT,
            with_payload=["chunk_id"],
            with_vectors=False,
        )
        chunk_to_point_id: dict[str, str] = {
            p.payload["chunk_id"]: str(p.id)
            for p in stored_points
            if p.payload and "chunk_id" in p.payload
        }
        synced_count = 0
        for symbol_key, symbol_data in symbols_map.items():
            if not symbol_data.get("vector_id") and symbol_key in chunk_to_point_id:
                symbol_data["vector_id"] = chunk_to_point_id[symbol_key]
                synced_count += 1
        if synced_count > 0:
            log.info(f"Synced {synced_count} existing vector IDs from Qdrant")
        return synced_count
    except Exception as e:
        log.warning(f"Could not sync existing vector IDs from Qdrant: {e}")
        return 0


# ID: 5140843f-a6d0-44e1-a592-2b82c33d7fa9
async def process_vectorization_task(
    task: dict,
    repo_root: Path,
    symbols_map: dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    dry_run: bool,
    failure_log_path: Path,
    verbose: bool,
    stored_chunks: dict[str, dict] | None = None,
) -> bool:
    """
    Process a single vectorization task. It assumes the decision to process has already been made.
    """
    cap_key = task["cap_key"]
    symbol_key = task["symbol_key"]

    try:
        source_code = extract_source_code(repo_root, symbols_map[symbol_key])
        if source_code is None:
            raise ValueError("Source code could not be extracted.")

        normalized_code = normalize_text(source_code)
        content_hash = sha256_hex(normalized_code)

        # The redundant skipping logic has been REMOVED.
        # This function now unconditionally processes the task it is given.

        log.debug(f"Processing chunk '{symbol_key}' (cap: {cap_key})")
        vector = await cognitive_service.get_embedding_for_code(normalized_code)

        payload_data = {
            "source_path": symbols_map[symbol_key].get("file"),
            "source_type": "code",
            "chunk_id": symbol_key,
            "content_sha256": content_hash,
            "language": "python",
            "symbol": symbol_key,
            "capability_tags": [cap_key],
            "model_rev": settings.EMBED_MODEL_REVISION,
        }

        if dry_run:
            symbols_map[symbol_key]["vector_id"] = f"dry_run_{symbol_key}"
            log.info(f"[DRY RUN] Would vectorize '{cap_key}' (chunk: {symbol_key})")
            return True

        point_id = await qdrant_service.upsert_capability_vector(
            vector=vector,
            payload_data=payload_data,
        )
        symbols_map[symbol_key].update(
            {
                "vector_id": str(point_id),
                "vectorized_at": datetime.now(UTC).isoformat(),
                "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                "model_revision": settings.EMBED_MODEL_REVISION,
                "content_hash": content_hash,
            }
        )
        log.debug(
            f"Successfully vectorized '{cap_key}' (chunk: {symbol_key}) with ID: {point_id}"
        )
        return True

    except Exception as e:
        log.error(f"Failed to process capability '{cap_key}': {e}")
        if not dry_run:
            log_failure(failure_log_path, cap_key, str(e), "knowledge_vectorize")
        if verbose:
            log.exception(f"Detailed error for '{cap_key}':")
        return False
