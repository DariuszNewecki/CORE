from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.sync_routes import sync_dev_sync


@pytest.mark.asyncio
# ID: a5b958a7-995d-48c3-b536-bed468e1166f
async def test_sync_dev_sync():
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_background_tasks = MagicMock()
    mock_payload = MagicMock()
    mock_session = MagicMock()
    expected_result = {"status": "queued", "sync_type": "dev_sync"}

    with patch(
        "api.v1.sync_routes._dispatch_sync",
        new_callable=AsyncMock,
        return_value=expected_result,
    ) as mock_dispatch:
        result = await sync_dev_sync(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
            payload=mock_payload,
            session=mock_session,
        )

    assert result == expected_result
    mock_dispatch.assert_awaited_once_with(
        sync_type="dev_sync",
        request=mock_request,
        response=mock_response,
        background_tasks=mock_background_tasks,
        payload=mock_payload,
        session=mock_session,
    )


from datetime import UTC, datetime
from uuid import uuid4

from api.v1.sync_routes import get_sync_run


# ID: 8e13b0eb-db66-4cd3-9c0d-947b9bc1674e
async def test_get_sync_run():
    run_id = uuid4()
    requested_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    started_at = datetime(2024, 1, 1, 12, 0, 5, tzinfo=UTC)
    finished_at = datetime(2024, 1, 1, 12, 0, 30, tzinfo=UTC)

    row = {
        "id": run_id,
        "sync_type": "full",
        "write": True,
        "target": "knowledge_graph",
        "status": "succeeded",
        "requested_by": "operator",
        "requested_at": requested_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": {"ok": True},
        "error": None,
    }

    mappings = MagicMock()
    mappings.first = MagicMock(return_value=row)
    result = MagicMock()
    result.mappings = MagicMock(return_value=mappings)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    response = await get_sync_run(run_id=run_id, session=session)

    session.execute.assert_awaited_once()
    assert response == {
        "run_id": str(run_id),
        "sync_type": "full",
        "write": True,
        "target": "knowledge_graph",
        "status": "succeeded",
        "requested_by": "operator",
        "requested_at": requested_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "result": {"ok": True},
        "error": None,
    }


import pytest

from api.v1.sync_routes import sync_code_vectors


@pytest.mark.asyncio
# ID: c8b68800-97f1-468b-a55a-9e6dc1caca63
async def test_sync_code_vectors():
    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock()
    payload = MagicMock()
    session = AsyncMock()

    expected = {"status": "ok", "sync_type": "code_vectors"}

    with patch(
        "api.v1.sync_routes._dispatch_sync", new=AsyncMock(return_value=expected)
    ) as mock_dispatch:
        result = await sync_code_vectors(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    mock_dispatch.assert_awaited_once_with(
        sync_type="code_vectors",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )
    assert result == expected


import pytest


@pytest.mark.asyncio
# ID: 174a4fc6-3ef3-4b20-bb09-125a3f0946bf
async def test_sync_vectors():
    from api.v1.sync_routes import sync_vectors

    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock()
    payload = MagicMock()
    session = MagicMock()

    expected = {"status": "dispatched", "sync_type": "vectors"}

    with patch(
        "api.v1.sync_routes._dispatch_sync", new=AsyncMock(return_value=expected)
    ) as mock_dispatch:
        result = await sync_vectors(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert result == expected
    mock_dispatch.assert_awaited_once_with(
        sync_type="vectors",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )



import pytest

from api.v1.sync_routes import sync_knowledge_graph


@pytest.mark.asyncio
# ID: 63d41b28-bcd5-415a-b90c-2119f258e59a
async def test_sync_knowledge_graph() -> None:
    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock()
    payload = MagicMock()
    session = MagicMock()

    expected_result = {"status": "dispatched", "sync_type": "knowledge_graph"}

    with patch(
        "api.v1.sync_routes._dispatch_sync",
        new=AsyncMock(return_value=expected_result),
    ) as mock_dispatch:
        result = await sync_knowledge_graph(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert result == expected_result
    mock_dispatch.assert_awaited_once_with(
        sync_type="knowledge_graph",
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )
