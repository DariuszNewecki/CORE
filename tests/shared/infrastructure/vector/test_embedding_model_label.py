"""A stored vector names the model that made it (#1390 F5).

The payload's ``model`` / ``model_rev`` came from two settings
(LOCAL_EMBEDDING_MODEL_NAME, EMBED_MODEL_REVISION) that nothing tied to the
Vectorizer role's real model: re-pointing the role to another model left
every new vector labelled with the old name.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from shared.infrastructure.llm.fallback_client import FallbackAwareLLMClient
from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.models.vector_models import VectorizableItem


def _client(model_name: str, *, quota_exhausted: bool = False) -> MagicMock:
    client = MagicMock()
    client.model_name = model_name
    if quota_exhausted:
        request = httpx.Request("POST", "https://example.test/embed")
        response = httpx.Response(status_code=429, request=request)
        client.get_embedding = AsyncMock(
            side_effect=httpx.HTTPStatusError("429", request=request, response=response)
        )
    else:
        client.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return client


def _factory(client: MagicMock):
    async def _build() -> MagicMock:
        return client

    return _build


def _cognitive(role_client: FallbackAwareLLMClient, revision: str | None) -> MagicMock:
    cognitive = MagicMock()
    cognitive.aget_vectorizer_client = AsyncMock(return_value=role_client)
    cognitive.get_embed_model_revision = AsyncMock(return_value=revision)
    return cognitive


# ID: 3f6d2a9c-7b1e-4e58-9c40-5a8e1d7b2f63
async def test_payload_names_the_model_that_served_the_embedding() -> None:
    role_client = FallbackAwareLLMClient(
        client_factories=[
            _factory(_client("first-embed", quota_exhausted=True)),
            _factory(_client("second-embed")),
        ],
        resource_names=["first", "second"],
    )
    qdrant = MagicMock()
    qdrant.upsert_symbol_vectors_bulk = AsyncMock()
    service = VectorIndexService(
        qdrant,
        "core_policies",
        embedder=CognitiveEmbedderAdapter(_cognitive(role_client, "2026-11-01")),
        vector_dim=3,
    )

    await service._process_batch(
        [VectorizableItem(item_id="p:1", text="policy text", payload={})]
    )

    kwargs = qdrant.upsert_symbol_vectors_bulk.await_args.kwargs
    assert kwargs["model"] == "second-embed"
    assert kwargs["model_rev"] == "2026-11-01"


# ID: 9a4c1e7b-2d5f-4b36-8e09-6c3f7a1d4b85
async def test_no_model_is_named_before_an_embedding_was_served() -> None:
    role_client = FallbackAwareLLMClient(
        client_factories=[_factory(_client("any-embed"))], resource_names=["only"]
    )
    adapter = CognitiveEmbedderAdapter(_cognitive(role_client, None))

    with pytest.raises(RuntimeError, match="unknown"):
        await adapter.model_identity()
