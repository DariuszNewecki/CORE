# tests/api/v1/test_coverage_routes.py

"""Unit tests for coverage_routes — ADR-057 Phase 3, D1.

Mocks the will.governance.coverage_runner facade so the assertions
target the route translation layer, not the underlying remediation
pipeline. Sessions are mocked AsyncSession instances. Covers ADR-057
verification criterion 2 (single-file generation for 2 distinct target
files + 1 batch path).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from api.v1.coverage_routes import (
    GenerateBatchRequest,
    GenerateRequest,
    InteractiveTestsRequest,
    coverage_check,
    coverage_gaps,
    coverage_history,
    coverage_methods,
    coverage_report,
    coverage_targets,
    generate_coverage,
    generate_coverage_batch,
    get_coverage_run,
    interactive_tests,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target_file",
    ["src/foo/bar.py", "src/will/governance/audit_runner.py"],
)
async def test_generate_inserts_pending_and_schedules_background(target_file):
    """POST /coverage/generate inserts a pending row, schedules a
    background task, and returns 202 + run_id + href. Exercises two
    distinct target_file values per ADR-057 verification #2."""
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

    payload = GenerateRequest(target_file=target_file, write=False)

    out = await generate_coverage(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/coverage/runs/{new_id}",
    }
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_batch_high_priority_inserts_and_schedules():
    """POST /coverage/generate:batch with priority='high' inserts a row
    (batch_priority='high', target_file=NULL) and schedules background
    execution. Closes ADR-057 verification #2 batch path."""
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

    payload = GenerateBatchRequest(priority="high", write=False)

    out = await generate_coverage_batch(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out["status"] == "pending"
    assert out["run_id"] == str(new_id)
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_generate_batch_unknown_priority_returns_422():
    """Unknown priority raises 422 without touching DB."""
    request = _mock_request_with_context()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()

    payload = GenerateBatchRequest(priority="bogus")

    with pytest.raises(HTTPException) as exc:
        await generate_coverage_batch(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )
    assert exc.value.status_code == 422
    session.execute.assert_not_awaited()
    background_tasks.add_task.assert_not_called()


@pytest.mark.asyncio
async def test_get_coverage_run_returns_row():
    """GET /coverage/runs/{id} returns the persisted row as a dict."""
    run_id = uuid4()
    session = AsyncMock()
    row = {
        "id": run_id,
        "target_file": "src/foo.py",
        "batch_priority": None,
        "write": False,
        "status": "completed",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": {"ok": True},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_coverage_run(run_id=run_id, session=session)
    assert out["run_id"] == str(run_id)
    assert out["target_file"] == "src/foo.py"
    assert out["status"] == "completed"


@pytest.mark.asyncio
async def test_get_coverage_run_returns_404_when_missing():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_coverage_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_coverage_check_delegates_to_facade():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_check",
        new=AsyncMock(return_value={"verdict": "PASS", "passed": True}),
    ) as facade:
        out = await coverage_check(request=request)
    facade.assert_awaited_once()
    assert out == {"verdict": "PASS", "passed": True}


@pytest.mark.asyncio
async def test_coverage_report_passes_show_missing():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_report",
        new=AsyncMock(return_value={"ok": True}),
    ) as facade:
        out = await coverage_report(request=request, show_missing=True)
    facade.assert_awaited_once()
    _, kwargs = facade.call_args
    assert kwargs.get("show_missing") is True
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_coverage_report_html_format_dispatches_to_html_runner():
    """format='html' routes to get_coverage_html_report instead of the text path. Closes #358."""
    request = _mock_request_with_context()
    html_payload = {"ok": True, "html_path": "htmlcov", "exit_code": 0}
    with (
        patch(
            "api.v1.coverage_routes.get_coverage_html_report",
            new=AsyncMock(return_value=html_payload),
        ) as html_facade,
        patch(
            "api.v1.coverage_routes.get_coverage_report",
            new=AsyncMock(return_value={"ok": True, "stdout_tail": []}),
        ) as text_facade,
    ):
        out = await coverage_report(request=request, show_missing=False, format="html")
    html_facade.assert_awaited_once()
    text_facade.assert_not_awaited()
    assert out == html_payload


@pytest.mark.asyncio
async def test_coverage_targets_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_targets",
        return_value={"path": ".intent/...", "targets": {}},
    ):
        out = await coverage_targets(request=request)
    assert "targets" in out


@pytest.mark.asyncio
async def test_coverage_gaps_passes_threshold_and_limit():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_gaps",
        new=AsyncMock(return_value={"threshold": 80.0, "count": 0, "gaps": []}),
    ) as facade:
        out = await coverage_gaps(request=request, threshold=80.0, limit=10)
    facade.assert_awaited_once()
    _, kwargs = facade.call_args
    assert kwargs["threshold"] == 80.0
    assert kwargs["limit"] == 10
    assert out["threshold"] == 80.0


@pytest.mark.asyncio
async def test_coverage_history_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_history",
        return_value={"count": 0, "history": []},
    ):
        out = await coverage_history(request=request, limit=5)
    assert out == {"count": 0, "history": []}


@pytest.mark.asyncio
async def test_coverage_methods_returns_descriptor():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_methods",
        return_value={"methods": []},
    ):
        out = await coverage_methods(request=request)
    assert "methods" in out


@pytest.mark.asyncio
async def test_tests_interactive_returns_inline_payload():
    """POST /tests/interactive returns the facade result inline (no row)."""
    request = _mock_request_with_context()
    payload = InteractiveTestsRequest(target_file="src/foo.py")
    with patch(
        "api.v1.coverage_routes.run_tests_interactive",
        new=AsyncMock(return_value={"ok": True}),
    ) as facade:
        out = await interactive_tests(request=request, payload=payload)
    facade.assert_awaited_once()
    assert out == {"ok": True}
