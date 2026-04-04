# repo_embedder/__init__.py
"""
Package split from repo_embedder.py.
"""

from __future__ import annotations

from .chunking_strategies import (
    _chunk_by_function,
    _chunk_by_heading,
    _chunk_by_symbol,
    _chunk_file,
    _chunk_whole,
    _split_large,
)
from .qdrant_upsert import _embed_and_upsert
from .repo_embedder_worker import RepoEmbedderWorker
