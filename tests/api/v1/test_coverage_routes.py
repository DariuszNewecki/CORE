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
    ReportRequest,
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
    request_coverage_report,
)


def _mock_request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


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


async def test_get_coverage_run_returns_404_when_missing():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)
    with pytest.raises(HTTPException) as exc:
        await get_coverage_run(run_id=uuid4(), session=session)
    assert exc.value.status_code == 404


async def test_coverage_check_delegates_to_facade():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_check",
        new=AsyncMock(return_value={"verdict": "PASS", "passed": True}),
    ) as facade:
        out = await coverage_check(request=request)
    facade.assert_awaited_once()
    assert out == {"verdict": "PASS", "passed": True}


async def test_coverage_report_returns_latest_persisted_report():
    """GET /coverage/report reads the latest completed run of the requested
    format via get_latest_coverage_report (#608: no inline pytest)."""
    session = AsyncMock()
    with patch(
        "api.v1.coverage_routes.get_latest_coverage_report",
        new=AsyncMock(return_value={"ok": True, "format": "text"}),
    ) as facade:
        out = await coverage_report(format="text", session=session)
    facade.assert_awaited_once()
    _, kwargs = facade.call_args
    assert kwargs.get("format") == "text"
    assert out == {"ok": True, "format": "text"}


async def test_coverage_report_404_when_no_persisted_report():
    """GET /coverage/report 404s (with a POST hint) when no completed run
    of the requested format exists yet."""
    session = AsyncMock()
    with patch(
        "api.v1.coverage_routes.get_latest_coverage_report",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc:
            await coverage_report(format="html", session=session)
    assert exc.value.status_code == 404


async def test_request_coverage_report_html_format_propagates_to_runner():
    """POST /coverage/reports inserts a pending run, schedules the background
    job, and propagates format='html' + show_missing to the runner. The html
    dispatch (#358) now lives on the background POST path after #608 moved
    pytest off the GET request thread."""
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

    payload = ReportRequest(format="html", show_missing=True)

    out = await request_coverage_report(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=payload,
        session=session,
    )

    assert out["run_id"] == str(new_id)
    assert out["status"] == "pending"
    assert response.status_code == 202
    background_tasks.add_task.assert_called_once()

    # Drive the scheduled closure to confirm it propagates the run's format
    # and show_missing through to run_and_persist_coverage_report.
    drive_report = background_tasks.add_task.call_args[0][0]

    async def _fake_bg_session():
        yield AsyncMock()

    with (
        patch(
            "api.v1.coverage_routes.open_background_session",
            new=_fake_bg_session,
        ),
        patch(
            "api.v1.coverage_routes.run_and_persist_coverage_report",
            new=AsyncMock(),
        ) as runner,
    ):
        await drive_report()

    runner.assert_awaited_once()
    _, kwargs = runner.call_args
    assert kwargs.get("format") == "html"
    assert kwargs.get("show_missing") is True
    assert kwargs.get("run_id") == new_id


def test_coverage_targets_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_targets",
        return_value={"path": ".intent/...", "targets": {}},
    ):
        out = coverage_targets(request=request)
    assert "targets" in out


def test_coverage_gaps_passes_threshold_and_limit():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_gaps",
        return_value={"threshold": 80.0, "count": 0, "gaps": []},
    ) as facade:
        out = coverage_gaps(request=request, threshold=80.0, limit=10)
    facade.assert_called_once()
    _, kwargs = facade.call_args
    assert kwargs["threshold"] == 80.0
    assert kwargs["limit"] == 10
    assert out["threshold"] == 80.0


def test_coverage_history_returns_facade_payload():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_history",
        return_value={"count": 0, "history": []},
    ):
        out = coverage_history(request=request, limit=5)
    assert out == {"count": 0, "history": []}


def test_coverage_methods_returns_descriptor():
    request = _mock_request_with_context()
    with patch(
        "api.v1.coverage_routes.get_coverage_methods",
        return_value={"methods": []},
    ):
        out = coverage_methods(request=request)
    assert "methods" in out


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
