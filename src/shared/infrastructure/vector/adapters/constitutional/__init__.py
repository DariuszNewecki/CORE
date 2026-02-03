# src/shared/infrastructure/vector/adapters/constitutional/__init__.py

"""
Constitutional vector adapter components.

Components:
- chunker: Semantic document chunking
- doc_key_resolver: Canonical key computation
- item_builder: VectorizableItem construction
- utils: Shared utilities
"""

from __future__ import annotations

from .chunker import chunk_document
from .doc_key_resolver import compute_doc_key
from .item_builder import data_to_items
from .utils import safe_str


__all__ = [
    "chunk_document",
    "compute_doc_key",
    "data_to_items",
    "safe_str",
]
