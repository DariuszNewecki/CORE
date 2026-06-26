# tests/api/v1/test_audit_remediations.py

"""Unit tests for POST/GET /audit/remediations — ADR-057 Phase 3, D4.

Covers ADR-057 verification criterion 4: all three modes ('safe',
'medium', 'all') accepted at the route layer; unknown modes → 422;
missing audit_run_id payload field → 422 (Pydantic validation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from pydantic import ValidationError

from api.v1.audit_routes import (
    CreateRemediationRequest,
    create_remediation_run,
    get_remediation_run,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


@pytest.mark.parametrize("mode", ["safe", "medium", "all"])
async def test_create_remediation_accepts_all_three_modes(mode):
    """ADR-057 verification #4: 'safe' | 'medium' | 'all' all dispatch
    successfully and 202."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 200
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    new_id = uuid4()
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    audit_run_id = uuid4()
    payload = CreateRemediationRequest(
        audit_run_id=audit_run_id, mode=mode, write=False
    )

    out = await create_remediation_run(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/audit/remediations/{new_id}",
    }
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()


async def test_create_remediation_unknown_mode_returns_422():
    """Unknown mode raises HTTPException(422) without touching DB."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()

    payload = CreateRemediationRequest(audit_run_id=uuid4(), mode="bogus", write=False)

    with pytest.raises(HTTPException) as exc:
        await create_remediation_run(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )
    assert exc.value.status_code == 422
    assert "bogus" in exc.value.detail["error"]
    session.execute.assert_not_awaited()
    background_tasks.add_task.assert_not_called()


def test_create_remediation_missing_audit_run_id_fails_validation():
    """Pydantic rejects bodies without audit_run_id (mapped to 422 by
    FastAPI's validator)."""
    with pytest.raises(ValidationError):
        CreateRemediationRequest(mode="safe", write=False)


async def test_get_remediation_returns_row():
    run_id = uuid4()
    audit_run_id = uuid4()
    session = AsyncMock()
    row = {
        "id": run_id,
        "audit_run_id": audit_run_id,
        "mode": "safe",
        "write": False,
        "status": "completed",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": {"fixes_succeeded": 0},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_remediation_run(run_id=run_id, session=session)
    assert out["run_id"] == str(run_id)
    assert out["audit_run_id"] == str(audit_run_id)
    assert out["mode"] == "safe"


async def test_get_remediation_returns_404_when_missing():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_remediation_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404
