# src/shared/models/vector_models.py

"""
Data models for the Unified Vector Indexing Service.

These models define the contract between domain adapters and the core
vectorization infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: fba05fa9-6379-4e23-9993-4d02af796264
class VectorizableItem:
    """
    Universal container for anything that can be vectorized.

    Domain adapters translate their specific data formats into this
    common representation, allowing the VectorIndexService to handle
    all vectorization uniformly.
    """

    item_id: str
    """Unique identifier (will be hashed to Qdrant point ID)"""

    text: str
    """The actual text content to vectorize"""

    payload: dict[str, Any]
    """Metadata to store alongside the vector"""

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.item_id:
            raise ValueError("item_id cannot be empty")
        if not self.text:
            raise ValueError("text cannot be empty")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dictionary")


@dataclass
# ID: f5a8418b-5180-45fb-8547-87cea637fcc8
class IndexResult:
    """
    Result of indexing a single item.

    Returned by VectorIndexService after successful upsert.
    """

    item_id: str
    """The original item ID"""

    point_id: int
    """The Qdrant point ID (hashed from item_id)"""

    vector_dim: int
    """Dimension of the stored vector"""
