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

from typing import Protocol

from shared.infrastructure.intent.operational_config import load_operational_config


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
