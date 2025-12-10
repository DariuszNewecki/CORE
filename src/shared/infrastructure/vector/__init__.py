# src/shared/infrastructure/vector/__init__.py

"""
Unified Vector Indexing Infrastructure

Provides the constitutional single source of truth for all vectorization
operations across CORE.
"""

from __future__ import annotations

from .vector_index_service import VectorIndexService


__all__ = ["VectorIndexService"]
