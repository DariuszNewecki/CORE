# tests/api/v1/test_audit_routes.py

"""Unit tests for audit_routes — ADR-054 Phase 1 (#335) + #340 closure.

Mocks `run_sync_audit` / `run_and_persist_audit` so the assertions
target the route translation layer, not the underlying audit
pipeline. Sessions are mocked AsyncSession instances.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from api.v1.audit_routes import (
    CreateAuditRunRequest,
    create_audit_run,
    get_audit_run,
)


async def test_create_audit_run_async_returns_pending_with_run_id():
    """`wait=false` path inserts a pending row, schedules background task,
    and returns {run_id, status:'pending'} with response.status_code 202."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
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

    payload = CreateAuditRunRequest(wait=False)

    out = await create_audit_run(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/v1/audit/runs/{new_id}",
    }
    assert background_tasks.add_task.call_count == 1
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_create_audit_run_sync_returns_full_result_inline():
    """`wait=true` path returns the run_sync_audit result dict in-band
    (status 200). The route is a pass-through to run_sync_audit."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    response = MagicMock(spec=Response)
    response.status_code = 200

    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()

    run_id = str(uuid4())
    sync_result = {
        "run_id": run_id,
        "verdict": "PASS",
        "passed": True,
        "stats": {},
        "findings": [],
        "executed_rule_ids": ["rule.a"],
        "auto_ignored": {},
        "duration_sec": 0.5,
    }

    payload = CreateAuditRunRequest(wait=True)

    with patch(
        "api.v1.audit_routes.run_sync_audit",
        AsyncMock(return_value=sync_result),
    ) as mock_sync:
        out = await create_audit_run(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert out == sync_result
    mock_sync.assert_awaited_once()
    # response.status_code is untouched — defaults to 200
    assert response.status_code == 200


async def test_get_audit_run_returns_full_record_with_findings():
    """GET returns the persisted row including the findings list
    (#340 closure: findings denormalized on audit_runs.findings)."""
    rid = uuid4()
    started_at = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 5, 17, 12, 1, 0, tzinfo=UTC)
    findings_payload = [
        {
            "check_id": "rule.a",
            "severity": "warning",
            "message": "example",
        }
    ]

    row = {
        "run_id": rid,
        "verdict": "PASS",
        "finding_count": 1,
        "blocking_count": 0,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "completed",
        "findings": findings_payload,
    }
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: row))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_audit_run(run_id=rid, session=session)

    assert out["run_id"] == str(rid)
    assert out["verdict"] == "PASS"
    assert out["finding_count"] == 1
    assert out["blocking_count"] == 0
    assert out["status"] == "completed"
    assert out["findings"] == findings_payload


async def test_get_audit_run_findings_defaults_to_empty_list_for_legacy_rows():
    """Pre-#340 rows have findings=None — route returns [] not null."""
    rid = uuid4()
    row = {
        "run_id": rid,
        "verdict": "PASS",
        "finding_count": 0,
        "blocking_count": 0,
        "started_at": datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC),
        "finished_at": datetime(2026, 5, 1, 0, 1, 0, tzinfo=UTC),
        "status": "completed",
        "findings": None,
    }
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: row))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_audit_run(run_id=rid, session=session)

    assert out["findings"] == []


async def test_get_audit_run_unknown_id_raises_404():
    """Unknown run_id raises HTTPException(404) with detail message."""
    rid = uuid4()
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: None))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    with pytest.raises(HTTPException) as exc_info:
        await get_audit_run(run_id=rid, session=session)

    assert exc_info.value.status_code == 404
    assert str(rid) in exc_info.value.detail
