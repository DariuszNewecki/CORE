# src/shared/utils/embedding_utils.py
"""
Provides utilities for handling text embeddings, including chunking and aggregation.
This module ensures that large documents can be processed reliably by embedding models.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from typing import List, Optional, Protocol

import httpx
import numpy as np

from shared.logger import getLogger

log = getLogger("embedding_utils")

# A reasonable chunk size to avoid overwhelming the embedding model
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50


# ID: f48d93d3-7ddf-4df2-8c10-dc63311b9485
class Embeddable(Protocol):
    """Defines the interface for any service that can create embeddings."""

    # ID: ac2f3e7e-34f5-44b6-80b1-dce2e7160c2e
    async def get_embedding(self, text: str) -> List[float]: ...


class _Adapter:
    """Internal adapter to make EmbeddingService conform to the Embeddable protocol."""

    def __init__(self, service):
        self._service = service

    # ID: 5a628ba4-df9b-4e8e-9ecc-9e74dc125b1f
    async def get_embedding(self, text: str) -> List[float]:
        return await self._service.get_embedding(text)


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
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


# ID: a652ae56-dc5d-47a9-90ea-7f873ca9239a
def normalize_text(text: str) -> str:
    """
    Applies a deterministic normalization process to text to ensure
    consistent hashing for content change detection.
    """
    if not isinstance(text, str):
        return ""
    # 1. Replace CRLF with LF
    # 2. Strip leading/trailing whitespace from the whole block
    # 3. Collapse multiple blank lines into a single blank line
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").strip())


# ID: 46703a51-3079-42fe-9bf7-e9724b009949
def sha256_hex(text: str) -> str:
    """Computes the SHA256 hex digest for a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =========================
# Provider-aware embedder
# =========================


# ID: 9b4a4f28-1e0a-4a2e-9c3f-9a1a5e3b3c1a
class EmbeddingService:
    """
    Provider-aware embedding client that conforms to the Embeddable protocol.

    - Ollama:   POST {base}/api/embeddings with {model, prompt}
    - OpenAI/DeepSeek: POST {base}/v1/embeddings with {model, input} (+ Authorization)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        api_key: Optional[str] = None,
    ) -> None:
        # Resolve provider + base/model from env with sensible defaults
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
            # Treat anything else as OpenAI-compatible (DeepSeek/API keys supported)
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
        log.info(f"EmbeddingService initialized for API at {self.base}")

    # ID: 8f5d2d61-1a1a-4e21-9c69-7a9e1d0ec0ab
    async def get_embedding(self, text: str) -> List[float]:
        """Return a single embedding vector for the given text."""
        url = f"{self.base}{self.endpoint}"
        payload = self._payload(text)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self.headers)

        if resp.status_code != 200:
            # Keep this error text shape (it matches what you saw in logs)
            log.error(
                f"HTTP error from embedding API: {resp.status_code} - {resp.text}"
            )
            raise RuntimeError(f"Embedding API HTTP {resp.status_code}")

        data = resp.json()
        vec = self._extract(data)
        if not vec:
            log.error("Embedding service returned no vector.")
            raise RuntimeError("No vector returned from embedding service")
        return vec  # type: ignore[return-value]


# ID: 6a1b6cde-0d0a-4e7c-8c4d-4f9a4fe0d6d1
def build_embedder_from_env() -> Embeddable:
    """
    Factory: builds an Embeddable using environment variables.
    This avoids a module-level `get_embedding` symbol (which caused duplication warnings).
    """
    return _Adapter(EmbeddingService())


# ID: 95c51c61-f288-483c-b76e-2915765004da
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
        # Should not happen with valid text, but as a safeguard
        raise ValueError("Cannot generate embedding for empty text.")

    embedding_tasks = [embedder.get_embedding(chunk) for chunk in chunks]
    chunk_vectors = await asyncio.gather(*embedding_tasks)

    # Convert list of lists to a 2D numpy array for easy averaging
    vector_array = np.array(chunk_vectors, dtype=np.float32)

    # Calculate the mean vector across the chunk dimension (axis=0)
    mean_vector = np.mean(vector_array, axis=0)

    # Normalize the final vector to unit length
    norm = np.linalg.norm(mean_vector)
    if norm == 0:
        return mean_vector  # Avoid division by zero

    normalized_vector = mean_vector / norm
    return normalized_vector
