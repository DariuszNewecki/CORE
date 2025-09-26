# src/shared/models/embedding_payload.py
"""
Defines the Pydantic model for the data payload associated with each
vector stored in the Qdrant database.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ID: 103f4a4c-a895-4de7-b5bf-ce230bcda4aa
class EmbeddingPayload(BaseModel):
    """
    Strict schema for the payload of every vector stored in Qdrant.
    This ensures all stored knowledge is traceable to its origin.
    """

    source_path: str = Field(..., description="Repo-relative path of the source file.")
    source_type: str = Field(
        ..., description="Type of content (e.g., 'code', 'intent')."
    )
    chunk_id: str = Field(
        ..., description="Stable locator for the text chunk (e.g., symbol key)."
    )
    content_sha256: str = Field(
        ..., description="Fingerprint of the normalized chunk text."
    )
    model: str = Field(..., description="Name of the embedding model used.")
    model_rev: str = Field(..., description="Pinned revision of the embedding model.")
    dim: int = Field(..., description="Dimensionality of the vector.")
    created_at: str = Field(..., description="ISO 8601 timestamp of vector creation.")

    # Optional fields for richer context
    language: Optional[str] = Field(None, description="Programming or markup language.")
    symbol: Optional[str] = Field(
        None, description="For code: fully qualified function/class name."
    )
    capability_tags: Optional[List[str]] = Field(
        None, description="Associated capability tags."
    )
