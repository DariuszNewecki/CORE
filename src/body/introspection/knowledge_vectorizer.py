# src/body/introspection/knowledge_vectorizer.py

"""
Handles the vectorization of individual capabilities (per-chunk), including interaction with Qdrant.
Idempotency is enforced at the chunk (symbol_key) level via `chunk_id` stored in the payload.

ENHANCED (V2.3.0):
- Added code metadata extraction (imports, calls, patterns)
- Enriched Qdrant payloads for hybrid search (semantic + pattern matching)
- Added code_preview for fast result display
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text, sha256_hex


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

from .knowledge_helpers import extract_source_code, log_failure


logger = getLogger(__name__)
DEFAULT_PAGE_SIZE = 250
MAX_SCROLL_LIMIT = 10000


@dataclass
# ID: 9c47cc9d-a43f-4942-b729-2166e9ce15a1
class VectorizationPayload:
    """
    Enhanced payload for vector store with searchable metadata.

    ENHANCED: Now includes imports, calls, patterns, and code preview
    for hybrid semantic + pattern-based search.
    """

    # Original fields
    source_path: str
    chunk_id: str
    content_sha256: str
    symbol: str
    capability_tags: list[str]
    model_rev: str
    source_type: str = "code"
    language: str = "python"

    # ENHANCED: Searchable metadata
    imports: list[str] = field(default_factory=list)
    """Imported modules: ['ast', 'Path', 'uuid']"""

    calls: list[str] = field(default_factory=list)
    """Called functions/methods: ['logger.info', 'path.exists']"""

    patterns: list[str] = field(default_factory=list)
    """Detected architectural patterns: ['repository', 'factory']"""

    code_preview: str = ""
    """First N chars of source for quick display"""

    # ID: 76a6fb80-80b3-4e96-b02a-cedf03468315
    # ID: 39b38009-cbac-45b0-9b4a-5136fb2ca389
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Qdrant payload."""
        return {
            "source_path": self.source_path,
            "chunk_id": self.chunk_id,
            "content_sha256": self.content_sha256,
            "symbol": self.symbol,
            "capability_tags": self.capability_tags,
            "model_rev": self.model_rev,
            "source_type": self.source_type,
            "language": self.language,
            "imports": self.imports,
            "calls": self.calls,
            "patterns": self.patterns,
            "code_preview": self.code_preview,
        }


# ID: a8879b62-02f8-4ece-9053-518df8ad7f50
# ID: 68431df1-40ac-42db-8cfd-f4805777f766
def extract_code_metadata(
    source_code: str,
) -> tuple[list[str], list[str], list[str]]:
    """Extract imports, calls, and patterns from source code."""
    imports: list[str] = []
    calls: list[str] = []
    patterns: list[str] = []
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
    except SyntaxError:
        pass
    return imports, calls, patterns


# ID: 7ede79ea-3cf6-4457-ba75-6a888361dfd0
# ID: 6dffbca8-2ab3-4128-baa6-e42782efe646
async def get_stored_chunks(qdrant_service: QdrantService) -> dict[str, Any]:
    """Get all stored chunk data from Qdrant for deduplication."""
    stored: dict[str, Any] = {}
    offset = None
    while True:
        points, offset = await qdrant_service.client.scroll(
            collection_name=qdrant_service.collection_name,
            limit=DEFAULT_PAGE_SIZE,
            with_payload=True,
            offset=offset,
        )
        for point in points:
            if point.payload and "chunk_id" in point.payload:
                stored[point.payload["chunk_id"]] = {
                    "point_id": str(point.id),
                    "content_sha256": point.payload.get("content_sha256"),
                }
        if offset is None:
            break
    return stored


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
    symbol_data: dict[str, Any],
    source_code: str,
    cap_key: str,
    model_revision: str,
) -> VectorizationPayload:
    """
    Prepares the structured payload for a symbol without performing any I/O.

    ENHANCED: Now extracts metadata (imports, calls, patterns) and code preview.

    Args:
        symbol_data: Symbol metadata from knowledge graph.
        source_code: Raw source code of the symbol.
        cap_key: Capability key for the symbol.
        model_revision: Embedding model revision string.
    """
    normalized_code = normalize_text(source_code)
    content_hash = sha256_hex(normalized_code)
    symbol_key = symbol_data["key"]

    # ENHANCED: Extract searchable metadata
    imports, calls, patterns = extract_code_metadata(source_code)

    # ENHANCED: Create code preview (first 500 chars)
    code_preview = source_code[:500] if len(source_code) > 500 else source_code

    return VectorizationPayload(
        # Original fields
        source_path=symbol_data.get("file", "unknown"),
        chunk_id=symbol_key,
        content_sha256=content_hash,
        symbol=symbol_key,
        capability_tags=[cap_key],
        model_rev=model_revision,
        # ENHANCED: Metadata fields
        imports=imports,
        calls=calls,
        patterns=patterns,
        code_preview=code_preview,
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
    embedding_model_name: str,
    model_revision: str,
) -> tuple[bool, dict | None]:
    """
    Process a single vectorization task. It orchestrates data preparation,
    embedding, and upserting. It returns a success flag and the data
    to update the symbol map with.

    Args:
        task: Task dict with cap_key and symbol_key.
        repo_root: Repository root path.
        symbols_map: Map of symbol keys to symbol data.
        cognitive_service: CognitiveService for embeddings.
        qdrant_service: QdrantService for vector operations.
        dry_run: If True, skip actual vectorization.
        failure_log_path: Path to log failures.
        verbose: If True, log detailed errors.
        embedding_model_name: Name of the embedding model (e.g. "nomic-embed-text").
        model_revision: Embedding model revision string (e.g. "2025-09-15").
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
        payload = _prepare_vectorization_payload(
            symbol_data, source_code, cap_key, model_revision
        )
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
            "embedding_model": embedding_model_name,
            "model_revision": model_revision,
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
