# src/shared/utils/embedding_utils.py

"""
Provides utilities for handling text embeddings, including chunking and aggregation.

CORE contract:
- "Embeddings" are produced by the Vectorizer role and are ALWAYS local.
- This module holds no embedding client of its own. The single sanctioned
  provider is CognitiveEmbedderAdapter (shared.infrastructure.vector.cognitive_adapter),
  which resolves host/model/timeout through the DB-backed Vectorizer role
  (core.llm_resources). Callers receive it via dependency injection.
- The former settings-based fallback (EmbeddingService / build_embedder_from_env)
  was removed: LOCAL_EMBEDDING_API_URL was never a declared Settings field, so the
  factory raised on every call and no caller reached it. The blocking rule
  architecture.boundary.embedding_access still names both symbols as a
  reintroduction guard.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Protocol

import numpy as np

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.utils.common_knowledge import normalize_text


_CFG_EMB = load_operational_config().embedding


# ID: 0c956ad0-a9d9-4cdf-bc8d-af9bccc4e30c
class Embeddable(Protocol):
    """Defines the interface for any service that can create embeddings."""

    # ID: 3ace367e-4136-4dd0-95b9-ec75462ff78d
    async def get_embedding(self, text: str) -> list[float]: ...


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Splits text into overlapping chunks."""
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += max(1, chunk_size - chunk_overlap)
    return chunks


# ID: 76aee7d7-fe49-4271-87b8-01fc9b074028
def sha256_hex(text: str) -> str:
    """Computes the SHA256 hex digest for a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ID: 31b34c50-e03b-4839-b588-d2a0c76a9004
async def chunk_and_embed(
    embedder: Embeddable,
    text: str,
    chunk_size: int = _CFG_EMB.chunk_size,
    chunk_overlap: int = _CFG_EMB.chunk_overlap,
) -> np.ndarray:
    """
    Chunks text, gets embeddings for each chunk in parallel, and returns the
    averaged embedding vector for the entire text.
    """
    text = normalize_text(text)
    chunks = _chunk_text(text, chunk_size, chunk_overlap)
    if not chunks:
        raise ValueError("Cannot generate embedding for empty text.")

    chunk_vectors = await asyncio.gather(*(embedder.get_embedding(c) for c in chunks))

    vector_array = np.array(chunk_vectors, dtype=np.float32)
    mean_vector = np.mean(vector_array, axis=0)

    norm = np.linalg.norm(mean_vector)
    if norm == 0:
        return mean_vector

    return mean_vector / norm
