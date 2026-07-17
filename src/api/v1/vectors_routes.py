# src/api/v1/vectors_routes.py

"""Vector store routes — diagnostic and management surface (ADR-146 D2).

Exposes:
- GET  /vectors/status        — list Qdrant collections with status
- POST /vectors/query         — semantic search over a named collection
- POST /vectors/rebuild       — delete collection + reset chunk_count (dry-run default)

CONSTITUTIONAL:
- Session acquired through api.dependencies only.
- No direct QdrantService import; instance provided via request.app.state.core_context.
- CognitiveEmbedderAdapter + VectorIndexService are shared/ imports (permitted in API).
- No settings imports.
- The destructive rebuild route carries per-route require_governor
  (architecture.api.sensitive_route_must_be_gated, ADR-132 placement contract; #803).
  No-op in OSS; core-platform mounts the real guard in Console mode.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, require_governor
from shared.context import CoreContext
from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger


logger = getLogger(__name__)

ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/vectors", tags=["Vectors"])

# ADR-132 D9 (#808): routes confirmed intentionally ungated, with rationale.
INTENTIONALLY_UNGATED: dict[str, str] = {
    "vector_query": (
        "Read-shaped: embeds the query and reads nearest vectors from Qdrant "
        "via service.query — no writes. Contrast the destructive vector_rebuild "
        "(gated, see module docstring): deletes a collection and resets "
        "chunk_count."
    ),
}

_COLLECTION_ALIASES: dict[str, str] = {
    "policies": "core_policies",
    "patterns": "core-patterns",
    "specs": "core_specs",
    "code": "core-code",
}


# ID: 255a09b3-1a10-4570-b4a9-860eeff8ae85
class VectorQueryRequest(BaseModel):
    query: str
    collection: str = "policies"
    limit: int = Field(default=5, ge=1, le=50)


# ID: cdf9bf8a-57c4-49d1-89be-656cc865f2a0
class VectorRebuildRequest(BaseModel):
    collection: str
    write: bool = False


@router.get("/status", summary="List Qdrant collections with status")
# ID: 133c2830-0294-4190-8c1a-dd489cdb1930
async def vector_status(request: Request) -> dict:
    """Return all active Qdrant collections with a liveness status."""
    core_context: CoreContext = request.app.state.core_context
    qdrant = core_context.qdrant_service
    if not qdrant:
        raise HTTPException(status_code=503, detail="Qdrant not configured.")
    try:
        collections = await qdrant.client.get_collections()
        return {
            "collections": [
                {"name": c.name, "status": "active"} for c in collections.collections
            ]
        }
    except Exception as exc:
        logger.warning("vector_status: Qdrant call failed: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Qdrant unavailable: {exc}"
        ) from exc


@router.post("/query", summary="Semantic search over a vector collection")
# ID: c3cb9ad8-4c79-4c14-afc4-9b63742a51fa
async def vector_query(body: VectorQueryRequest, request: Request) -> dict:
    """Embed the query and return the closest matches from the named collection.

    `collection` may be a short alias ('policies', 'patterns', 'specs', 'code')
    or the raw Qdrant collection name.
    Returns up to `limit` results ordered by descending similarity.
    """
    core_context: CoreContext = request.app.state.core_context
    qdrant = core_context.qdrant_service
    if not qdrant:
        raise HTTPException(status_code=503, detail="Qdrant not configured.")
    cognitive = core_context.cognitive_service
    if not cognitive:
        raise HTTPException(
            status_code=503,
            detail="Cognitive service not available — cannot embed query.",
        )
    collection_name = _COLLECTION_ALIASES.get(body.collection, body.collection)
    embedder = CognitiveEmbedderAdapter(cognitive)
    service = VectorIndexService(
        qdrant_service=qdrant,
        collection_name=collection_name,
        embedder=embedder,
    )
    results = await service.query(body.query, limit=body.limit)
    return {"results": results, "collection": collection_name, "count": len(results)}


@router.post(
    "/rebuild",
    summary="Delete a Qdrant collection and reset chunk_count",
    dependencies=[require_governor],
)
# ID: 02533572-d289-472f-a8c7-ddb122e81a97
async def vector_rebuild(
    body: VectorRebuildRequest,
    request: Request,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Delete a Qdrant collection and reset chunk_count so RepoEmbedderWorker repopulates.

    Dry-run by default — returns how many artifacts would be re-embedded.
    Pass write=true to apply (destructive: deletes the live collection).

    RepoEmbedderWorker recreates the collection with current vectors on its next cycle.
    """
    core_context: CoreContext = request.app.state.core_context
    qdrant = core_context.qdrant_service
    if not qdrant:
        raise HTTPException(status_code=503, detail="Qdrant not configured.")

    known = await qdrant.list_collections()
    if body.collection not in known:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown collection '{body.collection}'. "
            f"Known: {', '.join(sorted(known)) or '(none)'}",
        )

    row = (
        await session.execute(
            text(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE chunk_count > 0) AS embedded
                FROM core.repo_artifacts
                WHERE qdrant_collection = :c
                """
            ),
            {"c": body.collection},
        )
    ).one()
    total, embedded = row.total, row.embedded

    if not body.write:
        return {
            "collection": body.collection,
            "mode": "dry-run",
            "artifacts_total": total,
            "artifacts_to_reset": embedded,
        }

    await qdrant.client.delete_collection(collection_name=body.collection)

    result = await session.execute(
        text(
            """
            UPDATE core.repo_artifacts
            SET chunk_count = 0
            WHERE qdrant_collection = :c AND chunk_count > 0
            """
        ),
        {"c": body.collection},
    )
    await session.commit()
    reset_count = getattr(result, "rowcount", 0)

    return {
        "collection": body.collection,
        "mode": "write",
        "artifacts_reset": reset_count,
    }
