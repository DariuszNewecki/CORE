# src/features/introspection/vectorization/embedding_logic.py

"""Robust embedding strategies for the Will layer."""

from __future__ import annotations

import numpy as np

from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: a522d3cb-f244-4da7-bf81-9d148f98a0cb
async def get_robust_embedding(cog: CognitiveService, text: str) -> list[float]:
    """Handles standard embeddings + recursive split-retry for Ghost Vectors."""
    try:
        return await cog.get_embedding_for_code(text)
    except RuntimeError as e:
        if "Ghost Vector" in str(e) or "Embedding model failed" in str(e):
            logger.warning(
                "Ghost Vector detected (len=%d). Triggering split-strategy.", len(text)
            )
            mid = len(text) // 2
            v1 = await cog.get_embedding_for_code(text[:mid])
            v2 = await cog.get_embedding_for_code(text[mid:])
            if v1 and v2:
                avg = (np.array(v1) + np.array(v2)) / 2.0
                norm = np.linalg.norm(avg)
                return (avg / norm if norm > 0 else avg).tolist()
        raise e
