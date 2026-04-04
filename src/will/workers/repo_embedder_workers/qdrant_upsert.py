# qdrant_upsert.py
"""Handles Qdrant upsert operations for embedded chunks."""

from __future__ import annotations

from typing import Any


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

    points = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        embedding = await cognitive.get_embedding_for_code(text)
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
        await qdrant.upsert_points(
            collection_name=collection,
            points=points,
            wait=True,
        )

    return len(points)
