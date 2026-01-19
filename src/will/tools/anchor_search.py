# src/will/tools/anchor_search.py

"""
Searches for best module/layer placement based on code description.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from will.orchestration.cognitive_service import CognitiveService
from will.tools.anchors.storage import ANCHOR_COLLECTION


# ID: d190c672-96c7-4c23-b04d-f5e8a5b4382c
async def find_best_placement(
    code_description: str,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Find best placement for code based on description.

    First searches modules, falls back to layers if no module match found.
    """
    embedding = await cognitive_service.get_embedding_for_code(code_description)
    if not embedding:
        return []

    # Try module-level search first
    module_results = await qdrant_service.client.search(
        collection_name=ANCHOR_COLLECTION,
        query_vector=embedding,
        limit=limit * 2,
        query_filter={"must": [{"key": "type", "match": {"value": "module"}}]},
    )

    if module_results:
        return [
            {
                "score": hit.score,
                "type": "module",
                "path": hit.payload["path"],
                "name": hit.payload["name"],
                "purpose": hit.payload.get("purpose", ""),
                "layer": hit.payload["layer"],
                "confidence": "high" if hit.score > 0.5 else "medium",
            }
            for hit in module_results[:limit]
        ]

    # Fallback to layer-level search
    layer_results = await qdrant_service.client.search(
        collection_name=ANCHOR_COLLECTION,
        query_vector=embedding,
        limit=limit,
        query_filter={"must": [{"key": "type", "match": {"value": "layer"}}]},
    )

    return [
        {
            "score": hit.score,
            "type": "layer",
            "path": hit.payload["path"],
            "name": hit.payload["name"],
            "purpose": hit.payload["purpose"],
            "layer": hit.payload["name"],
            "confidence": "high" if hit.score > 0.5 else "medium",
        }
        for hit in layer_results
    ]
