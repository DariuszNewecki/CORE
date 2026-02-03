# src/shared/infrastructure/vector/adapters/constitutional/item_builder.py

"""
VectorizableItem Builder

Transforms constitutional document chunks into VectorizableItem objects
ready for vector storage.

Design:
- Input: Document data + metadata
- Output: List of VectorizableItem objects
- Delegates chunking to chunker module
- Delegates key computation to doc_key_resolver
- Pure transformation logic
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.vector.adapters.constitutional.chunker import chunk_document
from shared.infrastructure.vector.adapters.constitutional.doc_key_resolver import (
    compute_doc_key,
)
from shared.infrastructure.vector.adapters.constitutional.utils import safe_str
from shared.logger import getLogger
from shared.models.vector_models import VectorizableItem


logger = getLogger(__name__)


# ID: data-to-items
# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
def data_to_items(
    data: dict[str, Any],
    file_path: Path,
    doc_type: str,
    *,
    key_root: str,
    intent_root: Path,
) -> list[VectorizableItem]:
    """
    Convert document data to list of VectorizableItems.

    Process:
    1. Extract document metadata (id, version, title)
    2. Compute canonical doc_key
    3. Chunk document into semantic sections
    4. Build VectorizableItem for each chunk

    Args:
        data: Parsed document dict
        file_path: Path to source file
        doc_type: Document type (policy, constitution, standard, pattern)
        key_root: Root for key computation (policies, rules, constitution, standards)
        intent_root: Path to .intent/ directory

    Returns:
        List of VectorizableItem objects ready for indexing
    """
    # Extract document metadata
    doc_id = safe_str(data.get("id")) or file_path.stem
    doc_version = safe_str(data.get("version")) or "unknown"
    doc_title = safe_str(data.get("title")) or doc_id

    # Compute canonical key
    doc_key = compute_doc_key(file_path, key_root=key_root, intent_root=intent_root)

    # Chunk document
    chunks = chunk_document(data)

    # Build items
    items: list[VectorizableItem] = []
    for idx, chunk in enumerate(chunks):
        item = _chunk_to_item(
            chunk=chunk,
            idx=idx,
            doc_id=doc_id,
            doc_key=doc_key,
            doc_version=doc_version,
            doc_title=doc_title,
            doc_type=doc_type,
            file_path=file_path,
        )
        if item is not None:
            items.append(item)

    return items


# ID: chunk-to-item
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
def _chunk_to_item(
    *,
    chunk: dict[str, Any],
    idx: int,
    doc_id: str,
    doc_key: str,
    doc_version: str,
    doc_title: str,
    doc_type: str,
    file_path: Path,
) -> VectorizableItem | None:
    """
    Convert a single chunk to a VectorizableItem.

    Args:
        chunk: Chunk dict from chunker
        idx: Chunk index within document
        doc_id: Document ID
        doc_key: Canonical document key
        doc_version: Document version
        doc_title: Document title
        doc_type: Document type
        file_path: Source file path

    Returns:
        VectorizableItem or None if chunk has no content
    """
    content = safe_str(chunk.get("content", "")).strip()
    if not content:
        return None

    section_type = safe_str(chunk.get("section_type")) or "section"
    section_path = safe_str(chunk.get("section_path")) or section_type

    # Make item_id stable and collision-resistant
    # Format: {doc_key}:{section_type}:{index}
    item_id = f"{doc_key}:{section_type}:{idx}"

    # Compute content hash for deduplication
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Compute relative path for payload
    try:
        rel_path = file_path.relative_to(settings.REPO_PATH)
        rel_path_str = str(rel_path).replace("\\", "/")
    except Exception:
        rel_path_str = str(file_path).replace("\\", "/")

    # Build payload with metadata
    payload = {
        "doc_id": doc_id,
        "doc_key": doc_key,
        "doc_version": doc_version,
        "doc_title": doc_title,
        "doc_type": doc_type,
        "filename": file_path.name,
        "file_path": rel_path_str,
        "section_type": section_type,
        "section_path": section_path,
        "severity": safe_str(chunk.get("severity")) or "error",
        "content_sha256": content_hash,
    }

    return VectorizableItem(item_id=item_id, text=content, payload=payload)
