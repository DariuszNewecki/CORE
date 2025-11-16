# src/shared/utils/embedding_utils.py

"""
Provides utilities for handling text embeddings, including chunking and aggregation.
This module ensures that large documents can be processed reliably by embedding models.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Protocol

import httpx
import numpy as np

from shared.logger import getLogger
from shared.utils.common_knowledge import normalize_text

logger = getLogger(__name__)
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50


# ID: bcda4057-1723-4561-ba27-6ba7237ab7e4
class Embeddable(Protocol):
    """Defines the interface for any service that can create embeddings."""

    # ID: d8081706-92a9-4a15-beb3-5a7a5f54aeef
    async def get_embedding(self, text: str) -> list[float]: ...


class _Adapter:
    """Internal adapter to make EmbeddingService conform to the Embeddable protocol."""

    def __init__(self, service):
        self._service = service

    # ID: 2c4afbf8-98d6-489f-a6e8-b01dafa7310b
    async def get_embedding(self, text: str) -> list[float]:
        return await self._service.get_embedding(text)


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Splits text into overlapping chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += max(1, chunk_size - chunk_overlap)
    return chunks


# ID: 5e1666c2-1788-4610-89be-2056f51c8e09
def sha256_hex(text: str) -> str:
    """Computes the SHA256 hex digest for a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ID: 5fa5389d-3512-4579-9ff7-ee97bc744b71
class EmbeddingService:
    """
    Provider-aware embedding client that conforms to the Embeddable protocol.

    - Ollama:   POST {base}/api/embeddings with {model, prompt}
    - OpenAI/DeepSeek: POST {base}/v1/embeddings with {model, input} (+ Authorization)
    """

    def __init__(
        self,
        provider: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        api_key: str | None = None,
    ) -> None:
        self.provider = (
            provider or os.getenv("EMBEDDINGS_PROVIDER") or "ollama"
        ).lower()
        if self.provider == "ollama":
            self.base = (
                base_url
                or os.getenv("EMBEDDINGS_API_BASE")
                or os.getenv("LOCAL_EMBEDDING_API_URL")
                or "http://localhost:11434"
            ).rstrip("/")
            self.model = (
                model
                or os.getenv("EMBEDDINGS_MODEL")
                or os.getenv("LOCAL_EMBEDDING_MODEL_NAME")
                or "nomic-embed-text"
            )
            self.endpoint = "/api/embeddings"
            self.headers = {"Content-Type": "application/json"}
            self._payload = lambda text: {"model": self.model, "prompt": text}
            self._extract = lambda data: data.get("embedding")
        else:
            self.base = (
                base_url
                or os.getenv("DEEPSEEK_EMBEDDING_API_URL")
                or os.getenv("OPENAI_API_BASE")
                or "https://api.openai.com"
            ).rstrip("/")
            self.model = (
                model
                or os.getenv("DEEPSEEK_EMBEDDING_MODEL_NAME")
                or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            )
            key = (
                api_key
                or os.getenv("DEEPSEEK_EMBEDDING_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            )
            self.endpoint = "/v1/embeddings"
            self.headers = {"Content-Type": "application/json"}
            if key:
                self.headers["Authorization"] = f"Bearer {key}"
            self._payload = lambda text: {"model": self.model, "input": text}
            self._extract = lambda data: (data.get("data") or [{}])[0].get("embedding")
        self.timeout = timeout
        logger.info(f"EmbeddingService initialized for API at {self.base}")

    # ID: cf9b7923-3230-4681-8c1d-b5600fb37dca
    async def get_embedding(self, text: str) -> list[float]:
        """Return a single embedding vector for the given text."""
        url = f"{self.base}{self.endpoint}"
        payload = self._payload(text)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self.headers)
        if resp.status_code != 200:
            logger.error(
                f"HTTP error from embedding API: {resp.status_code} - {resp.text}"
            )
            raise RuntimeError(f"Embedding API HTTP {resp.status_code}")
        data = resp.json()
        vec = self._extract(data)
        if not vec:
            logger.error("Embedding service returned no vector.")
            raise RuntimeError("No vector returned from embedding service")
        return vec


# ID: dd4844fa-0993-4bd4-9bf4-8ca720e6f91e
def build_embedder_from_env() -> Embeddable:
    """
    Factory: builds an Embeddable using environment variables.
    This avoids a module-level `get_embedding` symbol (which caused duplication warnings).
    """
    return _Adapter(EmbeddingService())


# ID: dcb4acde-a396-48c0-8167-76041d114cc7
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
    embedding_tasks = [embedder.get_embedding(chunk) for chunk in chunks]
    chunk_vectors = await asyncio.gather(*embedding_tasks)
    vector_array = np.array(chunk_vectors, dtype=np.float32)
    mean_vector = np.mean(vector_array, axis=0)
    norm = np.linalg.norm(mean_vector)
    if norm == 0:
        return mean_vector
    normalized_vector = mean_vector / norm
    return normalized_vector
