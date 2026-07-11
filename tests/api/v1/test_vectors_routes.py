# tests/api/v1/test_vectors_routes.py

"""Tests for vectors routes — mock CoreContext, QdrantService, and VectorIndexService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.vectors_routes import vector_query, vector_rebuild, vector_status


def _make_request(qdrant=None, cognitive=None) -> MagicMock:
    ctx = MagicMock()
    ctx.app.state.core_context.qdrant_service = qdrant
    ctx.app.state.core_context.cognitive_service = cognitive
    return ctx


# ---------------------------------------------------------------------------
# vector_status
# ---------------------------------------------------------------------------


async def test_vector_status_returns_collections():
    qdrant = MagicMock()
    coll = MagicMock()
    coll.name = "core_policies"
    qdrant.client.get_collections = AsyncMock(
        return_value=MagicMock(collections=[coll])
    )
    result = await vector_status(request=_make_request(qdrant=qdrant))
    assert result["collections"][0]["name"] == "core_policies"


async def test_vector_status_503_when_no_qdrant():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await vector_status(request=_make_request(qdrant=None))
    assert exc_info.value.status_code == 503


async def test_vector_status_503_on_qdrant_error():
    from fastapi import HTTPException

    qdrant = MagicMock()
    qdrant.client.get_collections = AsyncMock(side_effect=RuntimeError("conn refused"))
    with pytest.raises(HTTPException) as exc_info:
        await vector_status(request=_make_request(qdrant=qdrant))
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# vector_query
# ---------------------------------------------------------------------------


async def test_vector_query_returns_results():
    qdrant = MagicMock()
    cognitive = MagicMock()
    request = _make_request(qdrant=qdrant, cognitive=cognitive)

    from api.v1.vectors_routes import VectorQueryRequest

    body = VectorQueryRequest(query="test query", collection="policies", limit=3)
    mock_results = [{"score": 0.9, "payload": {"doc_id": "doc1", "content": "hello"}}]

    with patch(
        "api.v1.vectors_routes.VectorIndexService"
    ) as MockVIS:
        inst = MagicMock()
        inst.query = AsyncMock(return_value=mock_results)
        MockVIS.return_value = inst
        with patch("api.v1.vectors_routes.CognitiveEmbedderAdapter"):
            result = await vector_query(body=body, request=request)

    assert result["count"] == 1
    assert result["collection"] == "core_policies"


async def test_vector_query_503_when_no_qdrant():
    from fastapi import HTTPException

    from api.v1.vectors_routes import VectorQueryRequest

    body = VectorQueryRequest(query="q")
    with pytest.raises(HTTPException) as exc_info:
        await vector_query(body=body, request=_make_request(qdrant=None))
    assert exc_info.value.status_code == 503


async def test_vector_query_503_when_no_cognitive():
    from fastapi import HTTPException

    from api.v1.vectors_routes import VectorQueryRequest

    body = VectorQueryRequest(query="q")
    with pytest.raises(HTTPException) as exc_info:
        await vector_query(
            body=body, request=_make_request(qdrant=MagicMock(), cognitive=None)
        )
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# vector_rebuild
# ---------------------------------------------------------------------------


async def test_vector_rebuild_dry_run():
    qdrant = MagicMock()
    qdrant.list_collections = AsyncMock(return_value=["core-code"])
    request = _make_request(qdrant=qdrant)
    session = MagicMock()
    row = MagicMock()
    row.total = 10
    row.embedded = 7
    session.execute = AsyncMock(return_value=MagicMock(one=MagicMock(return_value=row)))

    from api.v1.vectors_routes import VectorRebuildRequest

    body = VectorRebuildRequest(collection="core-code", write=False)
    result = await vector_rebuild(body=body, request=request, session=session)
    assert result["mode"] == "dry-run"
    assert result["artifacts_total"] == 10


async def test_vector_rebuild_404_unknown_collection():
    from fastapi import HTTPException

    qdrant = MagicMock()
    qdrant.list_collections = AsyncMock(return_value=["core-code"])
    request = _make_request(qdrant=qdrant)

    from api.v1.vectors_routes import VectorRebuildRequest

    body = VectorRebuildRequest(collection="nonexistent", write=False)
    with pytest.raises(HTTPException) as exc_info:
        await vector_rebuild(body=body, request=request, session=MagicMock())
    assert exc_info.value.status_code == 404
