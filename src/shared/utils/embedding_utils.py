# src/shared/utils/embedding_utils.py

"""
Provides utilities for handling text embeddings, including chunking and aggregation.

CORE contract:
- "Embeddings" are produced by the Vectorizer role and are ALWAYS local.
- No provider switching (no OpenAI/DeepSeek here).
- No os.getenv/os.environ.
- No fallback chains. Missing required settings => error.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Protocol

import httpx
import numpy as np

from shared.config import settings
from shared.logger import getLogger
from shared.utils.common_knowledge import normalize_text


logger = getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50


def _require_setting(name: str) -> str:
    """
    Strict settings read (CORE-style):
    - only from shared.config.settings (+ model_extra if used as backing store)
    - no fallback chains
    - missing/empty => ValueError
    """
    value = None

    if hasattr(settings, name):
        value = getattr(settings, name)
    else:
        extra = getattr(settings, "model_extra", {}) or {}
        value = extra.get(name)

    if value is None:
        raise ValueError(f"Missing required setting: {name}")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"Setting '{name}' is empty")

    return str(value)


# ID: 0c956ad0-a9d9-4cdf-bc8d-af9bccc4e30c
class Embeddable(Protocol):
    """Defines the interface for any service that can create embeddings."""

    # ID: 3ace367e-4136-4dd0-95b9-ec75462ff78d
    async def get_embedding(self, text: str) -> list[float]: ...


class _Adapter:
    """Internal adapter to make EmbeddingService conform to the Embeddable protocol."""

    def __init__(self, service: Embeddable):
        self._service = service

    # ID: f6d67bd8-83e2-42d5-81d3-07c668642568
    async def get_embedding(self, text: str) -> list[float]:
        return await self._service.get_embedding(text)


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


# ID: c3c32fe7-d434-43c6-b6a2-647afe213b4e
class EmbeddingService:
    """
    Local-only embeddings client (Vectorizer role contract).

    Expected settings (NO fallbacks):
    - LOCAL_EMBEDDING_API_URL
    - LOCAL_EMBEDDING_MODEL_NAME

    Endpoint:
    - POST {LOCAL_EMBEDDING_API_URL}/api/embeddings with {model, prompt}
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.base = _require_setting("LOCAL_EMBEDDING_API_URL").rstrip("/")
        self.model = _require_setting("LOCAL_EMBEDDING_MODEL_NAME")
        self.timeout = timeout

        self.endpoint = "/api/embeddings"
        self.headers: dict[str, str] = {"Content-Type": "application/json"}

        logger.info(
            "EmbeddingService initialized (local) base=%s model=%s",
            self.base,
            self.model,
        )

    # ID: b0db34ef-e89a-4910-b264-8e939cc14f9a
    async def get_embedding(self, text: str) -> list[float]:
        """Return a single embedding vector for the given text."""
        url = f"{self.base}{self.endpoint}"
        payload = {"model": self.model, "prompt": text}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self.headers)

        if resp.status_code != 200:
            logger.error(
                "HTTP error from local embedding API: %s - %s",
                resp.status_code,
                resp.text,
            )
            raise RuntimeError(f"Embedding API HTTP {resp.status_code}")

        data = resp.json()
        vec = data.get("embedding")
        if not vec:
            logger.error("Local embedding service returned no vector.")
            raise RuntimeError("No vector returned from embedding service")

        return vec


# ID: 14fd20cf-3101-4970-84b0-942ea9fffda3
def build_embedder_from_env() -> Embeddable:
    """
    Backwards-compatible factory name.

    CORE contract: this is settings-based and local-only.
    """
    return _Adapter(EmbeddingService())


# ID: 31b34c50-e03b-4839-b588-d2a0c76a9004
async def chunk_and_embed(
    embedder: Embeddable,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
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
