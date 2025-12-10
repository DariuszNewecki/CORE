# src/features/maintenance/scripts/vector_verify.py

"""Provides functionality for the vector_verify module."""

from __future__ import annotations

import asyncio

import numpy as np
from sqlalchemy import text

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: dfe4cf3f-0c40-4306-beb7-174a6683cdcf
async def verify():
    logger.info("Verifying Vector Distinctness...")
    qdrant = QdrantService()

    async with get_session() as s:
        # Get UUIDs for the formerly "ghost" symbols
        res = await s.execute(
            text(
                """
            SELECT qualname, id
            FROM core.symbols
            WHERE qualname IN ('feature', 'vectorize_patterns_cmd')
        """
            )
        )
        ids = {r.qualname: str(r.id) for r in res}

    if len(ids) != 2:
        logger.error("Could not find symbols in DB. Did you sync?")
        return

    # Fetch vectors
    v1 = np.array(await qdrant.get_vector_by_id(ids["feature"]))
    v2 = np.array(await qdrant.get_vector_by_id(ids["vectorize_patterns_cmd"]))

    # Calculate Similarity
    similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    logger.info(f"Target 1: feature ({ids['feature']})")
    logger.info(f"Target 2: vectorize_patterns_cmd ({ids['vectorize_patterns_cmd']})")
    logger.info(f"Cosine Similarity: {similarity:.6f}")

    if similarity < 0.999:
        logger.info("VERIFIED: Vectors are distinct. The fix worked.")
    else:
        logger.error("FAILURE: Vectors are still identical.")


if __name__ == "__main__":
    asyncio.run(verify())
