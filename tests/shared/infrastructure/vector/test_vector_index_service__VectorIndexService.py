# tests/shared/infrastructure/vector/test_vector_index_service__VectorIndexService.py

"""
VectorIndexService constructor contract: the Embeddable provider is injected,
never resolved from settings. There is no fallback factory
(architecture.boundary.embedding_access).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.infrastructure.vector.vector_index_service import VectorIndexService


class _StubEmbedder:
    async def get_embedding(self, text: str) -> list[float]:
        return [0.0] * 3


def test_constructs_with_injected_embedder() -> None:
    qdrant = MagicMock()
    embedder = _StubEmbedder()

    svc = VectorIndexService(
        qdrant_service=qdrant,
        collection_name="unit-test",
        embedder=embedder,
        vector_dim=3,
    )

    assert svc._embedder is embedder
    assert svc.vector_dim == 3
    assert svc.collection_name == "unit-test"


def test_embedder_is_required_keyword() -> None:
    """Omitting the embedder is a signature error, not a silent settings fallback."""
    with pytest.raises(TypeError):
        VectorIndexService(  # type: ignore[call-arg]
            qdrant_service=MagicMock(),
            collection_name="unit-test",
        )


def test_none_embedder_is_rejected_at_runtime() -> None:
    """Untyped callers passing None get a clear error instead of a lazy failure."""
    with pytest.raises(ValueError, match="requires an injected Embeddable"):
        VectorIndexService(
            qdrant_service=MagicMock(),
            collection_name="unit-test",
            embedder=None,  # type: ignore[arg-type]
        )


def test_vector_dim_defaults_from_settings() -> None:
    from shared.config import settings

    svc = VectorIndexService(
        qdrant_service=MagicMock(),
        collection_name="unit-test",
        embedder=_StubEmbedder(),
    )

    assert svc.vector_dim == int(settings.LOCAL_EMBEDDING_DIM)
