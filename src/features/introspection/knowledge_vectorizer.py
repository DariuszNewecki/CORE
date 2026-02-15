# src/features/introspection/knowledge_vectorizer.py

"""
Handles the vectorization of individual capabilities (per-chunk), including interaction with Qdrant.
Idempotency is enforced at the chunk (symbol_key) level via `chunk_id` stored in the payload.

ENHANCED (V2.7.0):
- Added code metadata extraction (imports, calls, patterns)
- Enriched Qdrant payloads for hybrid search (semantic + pattern matching)
- Added code_preview for fast result display
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
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
# ID: 006d4455-595b-45f7-94ee-5e1b9a86d5a9
# ID: ce415992-6d86-47ed-bbda-9aa7c9e5eb98
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
    """Function/method calls found: ['isinstance', 'Path.exists', 'logger.info']"""

    patterns: list[str] = field(default_factory=list)
    """Detected code patterns: ['isinstance_tuple', 'async_def', 'context_manager']"""

    code_preview: str = ""
    """First 500 chars of code for quick display"""

    # ID: 51941928-032a-46c5-9929-97392de7c174
    # ID: 05de316e-20e8-432a-aaaf-7c6853300e0c
    def to_dict(self) -> dict[str, Any]:
        """Converts the dataclass to a dictionary for Qdrant."""
        return {
            # Original fields
            "source_path": self.source_path,
            "source_type": self.source_type,
            "chunk_id": self.chunk_id,
            "content_sha256": self.content_sha256,
            "language": self.language,
            "symbol": self.symbol,
            "capability_tags": self.capability_tags,
            "model_rev": self.model_rev,
            # ENHANCED: Searchable metadata
            "imports": self.imports,
            "calls": self.calls,
            "patterns": self.patterns,
            "code_preview": self.code_preview,
        }


# ID: fa9f9456-cce6-4643-abbb-d49076dd3d5c
# ID: 46063755-09c3-4160-8e7e-90857cbdee8d
class CodeMetadataExtractor(ast.NodeVisitor):
    """
    Extracts searchable metadata from Python code via AST analysis.

    Collects:
    - imports: All imported modules
    - calls: All function/method calls
    - patterns: Detected code patterns
    """

    def __init__(self):
        self.imports: set[str] = set()
        self.calls: set[str] = set()
        self.patterns: set[str] = set()

    # ID: 89c71fe8-bc1f-4e0a-b948-c72d3d6c028f
    def visit_Import(self, node: ast.Import) -> None:
        """Track import statements."""
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])  # Base module
        self.generic_visit(node)

    # ID: b0eae9c5-fb6f-4eb2-aa00-14d85a2bf454
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from-import statements."""
        if node.module:
            self.imports.add(node.module.split(".")[0])  # Base module
        self.generic_visit(node)

    # ID: 19e8dcd7-046c-44c7-ad1a-484916475fa7
    def visit_Call(self, node: ast.Call) -> None:
        """Track function/method calls."""
        call_name = self._extract_call_name(node.func)
        if call_name:
            self.calls.add(call_name)

        # Pattern detection: isinstance with tuple
        if call_name == "isinstance" and len(node.args) >= 2:
            if isinstance(node.args[1], ast.Tuple):
                self.patterns.add("isinstance_tuple")

        self.generic_visit(node)

    # ID: 62c4c6d6-5e82-4243-ac56-1e426e0f3c19
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Detect async function pattern."""
        self.patterns.add("async_def")
        self.generic_visit(node)

    # ID: d9915d4a-e85e-4531-90f8-c54ab5787202
    def visit_With(self, node: ast.With) -> None:
        """Detect context manager pattern."""
        self.patterns.add("context_manager")
        self.generic_visit(node)

    # ID: 512a8b84-8982-4f1f-b692-c1c7b3f6c1f1
    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Detect async context manager pattern."""
        self.patterns.add("async_context_manager")
        self.generic_visit(node)

    def _extract_call_name(self, node: ast.AST) -> str | None:
        """Extract name from a Call's func node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # For method calls like logger.info, return full name
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            return node.attr
        return None


# ID: 7eba9307-d919-4fef-be54-25d2a7818947
def extract_code_metadata(source_code: str) -> tuple[list[str], list[str], list[str]]:
    """
    Extract searchable metadata from source code.

    Args:
        source_code: Python source code

    Returns:
        Tuple of (imports, calls, patterns)
    """
    try:
        tree = ast.parse(source_code)
        extractor = CodeMetadataExtractor()
        extractor.visit(tree)

        return (
            sorted(extractor.imports),
            sorted(extractor.calls),
            sorted(extractor.patterns),
        )
    except Exception as e:
        logger.debug("Metadata extraction failed: %s", e)
        return ([], [], [])


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

    ENHANCED: Now extracts metadata (imports, calls, patterns) and code preview.
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
        model_rev=settings.EMBED_MODEL_REVISION,
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
