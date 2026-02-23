# src/body/cli/logic/vector_drift.py

"""Provides functionality for the vector_drift module."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


async def _fetch_postgres_vector_ids() -> set[str]:
    """
    Authoritative source of vector IDs is the link table:
      core.symbol_vector_links(symbol_id UUID, vector_id TEXT, ...)
    """
    async with get_session() as session:
        rows = await session.execute(
            text("SELECT vector_id::text FROM core.symbol_vector_links")
        )
        return {r[0] for r in rows}


async def _fetch_qdrant_point_ids(qdrant_service: QdrantService) -> set[str]:
    """
    Fetch all point IDs from Qdrant without payloads/vectors.

    PHASE 1 FIX: Uses scroll_all_points() service method instead of direct client access.
    """
    points = await qdrant_service.scroll_all_points(
        with_payload=False, with_vectors=False
    )
    all_ids = {str(p.id) for p in points}
    return all_ids


# ID: fc322479-d062-486a-b2cc-636cd2eb7a86
async def inspect_vector_drift(context: CoreContext) -> dict:
    """
    Verifies synchronization between PostgreSQL and Qdrant using the
    context's QdrantService.

    Returns:
        dict: Contains synchronization results with keys:
            - postgres_count: Number of vector IDs in PostgreSQL
            - qdrant_count: Number of point IDs in Qdrant
            - missing_in_qdrant: List of IDs missing in Qdrant
            - orphans_in_qdrant: List of orphaned IDs in Qdrant
            - status: "synchronized" or "drift_detected"
            - error: Error message if any
    """
    logger.info("Verifying synchronization between PostgreSQL and Qdrant...")
    if context.qdrant_service is None and context.registry:
        try:
            context.qdrant_service = await context.registry.get_qdrant_service()
        except Exception as e:
            error_msg = f"Failed to initialize QdrantService: {e}"
            logger.error(error_msg)
            return {"error": error_msg, "status": "error"}
    if not context.qdrant_service:
        error_msg = "QdrantService not available in context."
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}
    try:
        postgres_ids, qdrant_ids = await asyncio.gather(
            _fetch_postgres_vector_ids(),
            _fetch_qdrant_point_ids(context.qdrant_service),
        )
    except Exception as e:
        error_msg = f"Error connecting to a database: {e}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}
    logger.info("Found %s linked vector IDs in PostgreSQL.", len(postgres_ids))
    logger.info("Found %s point IDs in Qdrant.", len(qdrant_ids))
    missing_in_qdrant = sorted(postgres_ids - qdrant_ids)
    orphans_in_qdrant = sorted(qdrant_ids - postgres_ids)
    result = {
        "postgres_count": len(postgres_ids),
        "qdrant_count": len(qdrant_ids),
        "missing_in_qdrant": missing_in_qdrant,
        "orphans_in_qdrant": orphans_in_qdrant,
        "status": (
            "synchronized"
            if not missing_in_qdrant and (not orphans_in_qdrant)
            else "drift_detected"
        ),
    }
    if not missing_in_qdrant and (not orphans_in_qdrant):
        logger.info(
            "Perfect synchronization. PostgreSQL and Qdrant are perfectly aligned."
        )
    else:
        if missing_in_qdrant:
            logger.warning(
                "Found %s vector IDs missing in Qdrant", len(missing_in_qdrant)
            )
        if orphans_in_qdrant:
            logger.warning(
                "Found %s orphaned point IDs in Qdrant", len(orphans_in_qdrant)
            )
    return result
