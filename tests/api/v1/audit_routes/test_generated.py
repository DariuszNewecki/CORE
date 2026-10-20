from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.audit_routes import create_remediation_run


@pytest.mark.asyncio
# ID: 972d5b25-d748-4565-9e67-0aa7fcc03de4
async def test_create_remediation_run():
    # Arrange
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_response = MagicMock(spec=Response)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    mock_payload = MagicMock()
    mock_payload.mode = "auto"
    mock_payload.audit_run_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_payload.write = True
    mock_payload.requested_by = "test_user"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = "550e8400-e29b-41d4-a716-446655440001"
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    with patch("api.v1.audit_routes.MODE_ALIASES", {"auto": "auto_mode"}):
        # Act
        result = await create_remediation_run(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
            payload=mock_payload,
            session=mock_session,
        )

    # Assert
    assert result["run_id"] == "550e8400-e29b-41d4-a716-446655440001"
    assert result["status"] == "pending"
    assert result["href"] == f"/v1/audit/remediations/{result['run_id']}"

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
    mock_background_tasks.add_task.assert_called_once()


from datetime import datetime
from uuid import uuid4

import pytest

from api.v1.audit_routes import get_remediation_run


@pytest.mark.asyncio
# ID: a0a0ddf1-3636-4c33-b6f0-c5c549953793
async def test_get_remediation_run():
    run_id = uuid4()
    audit_run_id = uuid4()
    requested_at = datetime(2024, 1, 1, 12, 0, 0)
    started_at = datetime(2024, 1, 1, 12, 1, 0)
    finished_at = datetime(2024, 1, 1, 12, 2, 0)

    row = {
        "id": run_id,
        "audit_run_id": audit_run_id,
        "mode": "apply",
        "write": True,
        "status": "completed",
        "requested_by": "user@example.com",
        "requested_at": requested_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": {"ok": True},
        "error": None,
    }

    mappings = MagicMock()
    mappings.first.return_value = row
    result = MagicMock()
    result.mappings.return_value = mappings

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    out = await get_remediation_run(run_id=run_id, session=session)

    session.execute.assert_awaited_once()
    assert out == {
        "run_id": str(run_id),
        "audit_run_id": str(audit_run_id),
        "mode": "apply",
        "write": True,
        "status": "completed",
        "requested_by": "user@example.com",
        "requested_at": requested_at.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "result": {"ok": True},
        "error": None,
    }


import uuid

from api.v1.audit_routes import CreateRemediationRequest


# ID: bb9ba714-e90c-41bb-b8df-b1c1d6de2e5e
def test_CreateRemediationRequest():
    audit_run_id = uuid.uuid4()
    request = CreateRemediationRequest(audit_run_id=audit_run_id)

    assert request.audit_run_id == audit_run_id
    assert request.mode == "safe"
    assert request.write is False
    assert request.requested_by == "api"

    custom = CreateRemediationRequest(
        audit_run_id=audit_run_id,
        mode="all",
        write=True,
        requested_by="tester",
    )
    assert custom.audit_run_id == audit_run_id
    assert custom.mode == "all"
    assert custom.write is True
    assert custom.requested_by == "tester"


from api.v1.audit_routes import get_audit_run


# ID: 0894bc7c-9371-4cfb-bdb2-3c5cffdfebcb
async def test_get_audit_run():
    run_id = uuid4()
    started = datetime(2024, 1, 1, 12, 0, 0)
    finished = datetime(2024, 1, 1, 12, 5, 0)

    row = {
        "run_id": run_id,
        "verdict": "fail",
        "finding_count": 3,
        "blocking_count": 2,
        "started_at": started,
        "finished_at": finished,
        "status": "completed",
        "findings": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}],
    }

    mock_result = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.first.return_value = row
    mock_result.mappings.return_value = mock_mappings

    session = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await get_audit_run(run_id=run_id, session=session)

    session.execute.assert_awaited_once()
    assert result["run_id"] == str(run_id)
    assert result["verdict"] == "fail"
    assert result["finding_count"] == 3
    assert result["blocking_count"] == 2
    assert result["started_at"] == started.isoformat()
    assert result["finished_at"] == finished.isoformat()
    assert result["status"] == "completed"
    assert result["findings"] == row["findings"]


from datetime import UTC

import pytest

from api.v1.audit_routes import list_audit_runs


@pytest.mark.asyncio
# ID: 0c5b1700-5503-4bbb-9fd7-4f4819e18a4d
async def test_list_audit_runs() -> None:
    started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    finished = datetime(2024, 1, 1, 12, 5, 0, tzinfo=UTC)

    row = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "verdict": "pass",
        "finding_count": 3,
        "blocking_count": 0,
        "started_at": started,
        "finished_at": finished,
        "status": "completed",
    }

    mappings = MagicMock()
    mappings.all.return_value = [row]
    result = MagicMock()
    result.mappings.return_value = mappings

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    response = await list_audit_runs(limit=50, after=None, session=session)

    session.execute.assert_awaited_once()
    assert response["count"] == 1
    assert response["has_more"] is False
    assert response["next_cursor"] is None
    assert response["runs"] == [
        {
            "run_id": "11111111-1111-1111-1111-111111111111",
            "verdict": "pass",
            "finding_count": 3,
            "blocking_count": 0,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "status": "completed",
        }
    ]
