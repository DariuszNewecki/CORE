# tests/shared/utils/test_embedding_utils.py

"""
shared.utils.embedding_utils: chunking/aggregation helpers only.

The settings-based embedder (EmbeddingService / build_embedder_from_env) was
removed -- LOCAL_EMBEDDING_API_URL was never a declared Settings field, so the
factory raised on every call. These tests pin the surviving surface and guard
against the dead path being reintroduced.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.utils import embedding_utils
from shared.utils.embedding_utils import _chunk_text, chunk_and_embed, sha256_hex


class _StubEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0, 0.0]


def test_settings_based_embedder_is_gone() -> None:
    assert not hasattr(embedding_utils, "EmbeddingService")
    assert not hasattr(embedding_utils, "build_embedder_from_env")
    assert not hasattr(embedding_utils, "_require_setting")


def test_chunk_text_overlaps() -> None:
    chunks = _chunk_text("abcdefghij", chunk_size=4, chunk_overlap=1)
    assert chunks == ["abcd", "defg", "ghij", "j"]
    assert _chunk_text("", 4, 1) == []


def test_sha256_hex_is_stable() -> None:
    assert sha256_hex("core") == sha256_hex("core")
    assert len(sha256_hex("core")) == 64


async def test_chunk_and_embed_averages_and_normalizes() -> None:
    embedder = _StubEmbedder()
    vec = await chunk_and_embed(embedder, "hello world", chunk_size=5, chunk_overlap=0)

    assert len(embedder.calls) >= 2
    assert vec.dtype == np.float32
    assert np.isclose(np.linalg.norm(vec), 1.0)


async def test_chunk_and_embed_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="empty text"):
        await chunk_and_embed(_StubEmbedder(), "   ")
