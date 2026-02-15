# src/features/maintenance/scripts/vector_verify.py
"""
Vector verification maintenance script.

Constitutional constraints:
- No direct instantiation of QdrantService. Must be resolved via DI/registry.
- This script is orchestration logic; it must use existing services.
"""

from __future__ import annotations

from shared.context import CoreContext
from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 0d7a1b4f-6d7f-4d5c-a6f6-5f7d2b0a9c2a
async def run_vector_verify(context: CoreContext) -> dict[str, int]:
    """
    Verifies vector store consistency via the sanctioned service layer.

    Returns:
        A small summary dict with counts (kept intentionally stable for CLI consumption).
    """
    if context is None:
        raise ValueError("CoreContext is required")

    # Resolve QdrantService via DI
    qdrant_service = getattr(context, "qdrant_service", None)
    if qdrant_service is None:
        registry = getattr(context, "registry", None)
        if registry is None:
            raise RuntimeError(
                "No qdrant_service on context and no registry available to resolve it."
            )
        qdrant_service = await registry.get_qdrant_service()
        context.qdrant_service = qdrant_service

    # Delegate to service methods only (no direct qdrant_service.client.* usage here)
    # NOTE: Adapt these calls to the actual methods you expose (names below are intentionally generic).
    stats: dict[str, int] = {
        "points_total": 0,
        "points_orphaned": 0,
        "links_total": 0,
    }

    try:
        # If your QdrantService exposes collection stats:
        if hasattr(qdrant_service, "count_points"):
            stats["points_total"] = int(await qdrant_service.count_points())
        # If your QdrantService exposes orphan detection:
        if hasattr(qdrant_service, "count_orphaned_points"):
            stats["points_orphaned"] = int(await qdrant_service.count_orphaned_points())
    except Exception as e:
        logger.warning("Vector verify: unable to read Qdrant counts: %s", e)

    # Postgres link stats should be obtained via your existing DB service layer;
    # keep this script minimal and constitutional.
    try:
        kg = getattr(context, "knowledge_service", None)
        if kg and hasattr(kg, "count_vector_links"):
            stats["links_total"] = int(await kg.count_vector_links())
    except Exception as e:
        logger.warning("Vector verify: unable to read DB link counts: %s", e)

    logger.info(
        "Vector verify summary: points_total=%s, points_orphaned=%s, links_total=%s",
        stats["points_total"],
        stats["points_orphaned"],
        stats["links_total"],
    )
    return stats
