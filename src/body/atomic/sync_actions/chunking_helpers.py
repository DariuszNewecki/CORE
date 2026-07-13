# src/body/atomic/sync_actions/chunking_helpers.py
# chunking_helpers.py
"""Module-level chunking and embedding helpers are standalone utilities used by the vector sync actions; they share no state with the action functions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config


_CFG_CHK = load_operational_config().chunking


def _chunk_file(file_path: Path, artifact_type: str) -> list[dict[str, Any]]:
    """Chunk a file into semantic units. Returns list of {text, metadata} dicts."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = str(file_path)
    if artifact_type == "python":
        return _chunk_by_symbol(content, rel_path)
    elif artifact_type in ("doc", "report", "infra"):
        return _chunk_by_heading(content, rel_path)
    elif artifact_type == "test":
        return _chunk_by_function(content, rel_path)
    elif artifact_type == "prompt":
        return _chunk_whole(content, rel_path)
    elif artifact_type == "intent":
        return _chunk_by_heading(content, rel_path)
    else:
        return _chunk_by_heading(content, rel_path)


def _chunk_by_symbol(content: str, source: str) -> list[dict[str, Any]]:
    """Chunk Python source by top-level class and function boundaries using AST."""
    import ast as _ast

    chunks = []
    lines = content.splitlines()
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return _chunk_by_heading(content, source)

    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno or (start + 30)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(
                    _split_large(text, source, node.name, chunk_type="function")
                )
        elif isinstance(node, _ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno or (start + 50)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(_split_large(text, source, node.name, chunk_type="class"))

    if not chunks:
        return _chunk_whole(content, source)
    return chunks


def _chunk_by_heading(content: str, source: str) -> list[dict[str, Any]]:
    """Split markdown/YAML by headings or top-level keys."""
    chunks = []
    current_heading = "intro"
    current_text: list[str] = []

    for line in content.splitlines():
        if line.startswith("#"):
            if current_text:
                text = "\n".join(current_text).strip()
                if text:
                    chunks.extend(_split_large(text, source, current_heading))
            current_heading = line.lstrip("#").strip()
            current_text = [line]
        else:
            current_text.append(line)

    if current_text:
        text = "\n".join(current_text).strip()
        if text:
            chunks.extend(_split_large(text, source, current_heading))

    return chunks


def _chunk_by_function(content: str, source: str) -> list[dict[str, Any]]:
    """Split Python test files by test function boundaries."""
    import ast as _ast

    chunks = []
    lines = content.splitlines()
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return _chunk_by_heading(content, source)

    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                start = node.lineno - 1
                end = node.end_lineno or (start + 20)
                text = "\n".join(lines[start:end]).strip()
                if text:
                    chunks.append(
                        {
                            "text": text,
                            "metadata": {
                                "source": source,
                                "section": node.name,
                                "chunk_type": "test_function",
                            },
                        }
                    )

    if not chunks:
        return _chunk_by_heading(content, source)
    return chunks


def _chunk_whole(content: str, source: str) -> list[dict[str, Any]]:
    """Treat small files as a single chunk.

    Empty/whitespace-only content yields no chunks — not a single
    empty-text chunk — so callers' `if not chunks: mark_artifact_empty()`
    guard can reach permanently-skipped instead of looping forever (the
    embedder short-circuits empty text to `None`, which `_embed_and_upsert`
    silently drops, leaving chunk_count stuck at 0).
    """
    stripped = content.strip()
    if not stripped:
        return []
    return _split_large(stripped, source, "full")


def _split_large(
    text: str,
    source: str,
    section: str,
    chunk_type: str = "section",
) -> list[dict[str, Any]]:
    """Split text that exceeds _CFG_CHK.max_chunk_chars into overlapping sub-chunks."""
    if len(text) <= _CFG_CHK.max_chunk_chars:
        return [
            {
                "text": text,
                "metadata": {
                    "source": source,
                    "section": section,
                    "chunk_type": chunk_type,
                },
            }
        ]
    chunks = []
    step = _CFG_CHK.max_chunk_chars - 200  # 200-char overlap
    for i, start in enumerate(range(0, len(text), step)):
        chunk_text = text[start : start + _CFG_CHK.max_chunk_chars].strip()
        if chunk_text:
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "source": source,
                        "section": f"{section}_part{i}",
                        "chunk_type": chunk_type,
                    },
                }
            )
    return chunks


async def _embed_and_upsert(
    chunks: list[dict[str, Any]],
    collection: str,
    file_path: str,
    artifact_type: str,
    qdrant: Any,
    cognitive: Any,
) -> int:
    """Embed chunks and upsert to Qdrant. Returns number of chunks upserted."""
    from qdrant_client import models as qm

    from shared.universal import get_deterministic_id

    await qdrant.ensure_collection(collection_name=collection)

    # Concurrency is bounded by the Vectorizer LLMClient's
    # asyncio.Semaphore(max_concurrent) at the resource layer, so the
    # gather here can fan out the full chunk list without overrunning the
    # embedding host. Order is preserved, so the deterministic chunk
    # index (used to build the Qdrant point ID) stays stable.
    embeddings = await asyncio.gather(
        *(cognitive.get_embedding_for_code(c["text"]) for c in chunks)
    )

    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding is None:
            continue
        item_id = f"{file_path}::chunk::{i}"
        point_id = get_deterministic_id(item_id)
        payload = {
            **chunk["metadata"],
            "item_id": item_id,
            "artifact_type": artifact_type,
            "file_path": file_path,
        }
        points.append(
            qm.PointStruct(
                id=point_id,
                vector=(
                    embedding.tolist()
                    if hasattr(embedding, "tolist")
                    else list(embedding)
                ),
                payload=payload,
            )
        )

    if points:
        await qdrant.upsert_points(collection_name=collection, points=points, wait=True)

    return len(points)
