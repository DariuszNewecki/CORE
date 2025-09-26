# src/shared/utils/embedding_utils.py
"""
Provides utilities for handling text embeddings, including chunking and aggregation.
This module ensures that large documents can be processed reliably by embedding models.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from typing import List, Protocol

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
        start += chunk_size - chunk_overlap
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
