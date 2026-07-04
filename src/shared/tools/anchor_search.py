# src/shared/tools/anchor_search.py
"""Searches for best module/layer placement based on code description."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import qdrant_client.models as qm

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.tools.anchors.storage import ANCHOR_COLLECTION


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService


# ID: d190c672-96c7-4c23-b04d-f5e8a5b4382c
async def find_best_placement(
    code_description: str,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Find best placement for code based on description.

    First searches modules, falls back to layers if no module match found.
    """
    embedding = await cognitive_service.get_embedding_for_code(code_description)
    if not embedding:
        return []

    module_results = await qdrant_service.search(
        collection_name=ANCHOR_COLLECTION,
        query_vector=embedding,
        limit=limit * 2,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="type", match=qm.MatchValue(value="module"))]
        ),
    )

    if module_results:
        return [
            {
                "score": hit.score,
                "type": "module",
                "path": (hit.payload or {}).get("path", ""),
                "name": (hit.payload or {}).get("name", ""),
                "purpose": (hit.payload or {}).get("purpose", ""),
                "layer": (hit.payload or {}).get("layer", ""),
                "confidence": "high" if hit.score > 0.5 else "medium",
            }
            for hit in module_results[:limit]
            if hit.payload
        ]

    layer_results = await qdrant_service.search(
        collection_name=ANCHOR_COLLECTION,
        query_vector=embedding,
        limit=limit,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="type", match=qm.MatchValue(value="layer"))]
        ),
    )

    return [
        {
            "score": hit.score,
            "type": "layer",
            "path": (hit.payload or {}).get("path", ""),
            "name": (hit.payload or {}).get("name", ""),
            "purpose": (hit.payload or {}).get("purpose", ""),
            "layer": (hit.payload or {}).get("name", ""),
            "confidence": "high" if hit.score > 0.5 else "medium",
        }
        for hit in layer_results
        if hit.payload
    ]
