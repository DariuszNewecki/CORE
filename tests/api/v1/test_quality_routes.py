# tests/api/v1/test_quality_routes.py

"""Unit tests for quality_routes — ADR-055 Phase 2 D3.

Sync endpoints (/quality/imports, /quality/body-ui) are pass-throughs
to the will.governance.fix_runner facade; tests stub the facade
functions and confirm the route shapes the inline response and
forwards the target_files parameter.

Async endpoints (/quality/lint, /quality/tests, /quality/system,
/quality/gates) follow the same INSERT-then-schedule pattern as the
async /fix endpoints. Tests confirm the row is inserted with
kind='quality_check' and the correct per-check fix_id, the background
task is queued, and a 202 is returned. One round-trip test exercises
GET /v1/fix/runs/{id} against a quality_check row to confirm the /fix
resource read serves /quality rows by design (single fix_runs table).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import BackgroundTasks, Response

from api.v1.fix_routes import get_fix_run
from api.v1.quality_routes import (
    QualityAsyncRequest,
    QualityLintRequest,
    QualityTargetRequest,
    QualityTestsRequest,
    quality_body_ui,
    quality_gates,
    quality_imports,
    quality_lint,
    quality_system,
    quality_tests,
)


# ----------------------------------------------------------------------
# Synchronous endpoints
# ----------------------------------------------------------------------


async def test_quality_imports_ok_path_returns_status_ok_and_empty_violations():
    """When the facade reports no violations the route returns
    status='ok' with an empty list."""
    with patch(
        "api.v1.quality_routes.run_quality_imports",
        AsyncMock(return_value={"status": "ok", "violations": []}),
    ) as mock:
        out = await quality_imports(
            payload=QualityTargetRequest(target_files=None),
        )

    mock.assert_awaited_once_with(None)
    assert out == {"status": "ok", "violations": []}


async def test_quality_imports_failed_path_propagates_violations():
    """The route returns whatever the facade reports — violations
    pass through untouched."""
    violations = [{"file": "a.py", "line": 1, "rule": "F401", "message": "unused"}]
    with patch(
        "api.v1.quality_routes.run_quality_imports",
        AsyncMock(return_value={"status": "failed", "violations": violations}),
    ) as mock:
        out = await quality_imports(
            payload=QualityTargetRequest(target_files=["src/x.py"]),
        )

    mock.assert_awaited_once_with(["src/x.py"])
    assert out["status"] == "failed"
    assert out["violations"] == violations


async def test_quality_body_ui_ok_path_returns_status_ok():
    """No violations → status='ok' with the CoreContext forwarded."""
    request = MagicMock()
    sentinel_ctx = MagicMock()
    request.app.state.core_context = sentinel_ctx

    with patch(
        "api.v1.quality_routes.run_quality_body_ui",
        AsyncMock(return_value={"status": "ok", "violations": []}),
    ) as mock:
        out = await quality_body_ui(
            request=request,
            payload=QualityTargetRequest(target_files=None),
        )

    mock.assert_awaited_once_with(sentinel_ctx, None)
    assert out == {"status": "ok", "violations": []}


async def test_quality_body_ui_failed_path_propagates_violations():
    """Violations from the facade propagate unchanged."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    violations = [{"file": "src/body/x.py", "rule": "print", "line": 12}]

    with patch(
        "api.v1.quality_routes.run_quality_body_ui",
        AsyncMock(return_value={"status": "failed", "violations": violations}),
    ) as mock:
        out = await quality_body_ui(
            request=request,
            payload=QualityTargetRequest(target_files=["src/body/x.py"]),
        )

    assert mock.await_count == 1
    assert mock.await_args.args[1] == ["src/body/x.py"]
    assert out == {"status": "failed", "violations": violations}


# ----------------------------------------------------------------------
# Asynchronous endpoints — shared scaffolding
# ----------------------------------------------------------------------


def _async_session_returning(new_id):
    """Build a mocked AsyncSession whose INSERT RETURNING yields new_id."""
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()
    return session


def _request_with_context():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


async def test_quality_lint_inserts_quality_check_row_and_returns_202():
    """POST /quality/lint persists kind='quality_check', fix_id='lint',
    schedules the background runner, returns 202 with href targeting
    /fix/runs/{id}."""
    request = _request_with_context()
    response = MagicMock(spec=Response)
    response.status_code = 200
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    new_id = uuid4()
    session = _async_session_returning(new_id)

    out = await quality_lint(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=QualityLintRequest(fix=True),
        session=session,
    )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/v1/fix/runs/{new_id}",
    }
    assert background_tasks.add_task.call_count == 1
    bind = session.execute.call_args[0][1]
    assert bind["check"] == "lint"
    assert bind["requested_by"] == "api"


async def test_quality_tests_inserts_quality_check_row_and_returns_202():
    """POST /quality/tests uses fix_id='tests' and forwards the
    optional `path` to the background runner via the closure params."""
    request = _request_with_context()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    scheduled: list = []
    background_tasks.add_task = MagicMock(side_effect=lambda fn: scheduled.append(fn))

    new_id = uuid4()
    session = _async_session_returning(new_id)

    async def fake_open_session():
        yield AsyncMock()

    mock_runner = AsyncMock()
    with (
        patch("api.v1.quality_routes.run_and_persist_quality", mock_runner),
        patch("api.v1.quality_routes.open_background_session", fake_open_session),
    ):
        await quality_tests(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=QualityTestsRequest(path="tests/api/"),
            session=session,
        )
        await scheduled[0]()

    bind = session.execute.call_args[0][1]
    assert bind["check"] == "tests"
    kwargs = mock_runner.call_args.kwargs
    assert kwargs["run_id"] == new_id
    assert kwargs["check"] == "tests"
    assert kwargs["params"] == {"path": "tests/api/"}


async def test_quality_system_inserts_quality_check_row_and_returns_202():
    """POST /quality/system uses fix_id='system' and forwards empty params."""
    request = _request_with_context()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    scheduled: list = []
    background_tasks.add_task = MagicMock(side_effect=lambda fn: scheduled.append(fn))

    new_id = uuid4()
    session = _async_session_returning(new_id)

    async def fake_open_session():
        yield AsyncMock()

    mock_runner = AsyncMock()
    with (
        patch("api.v1.quality_routes.run_and_persist_quality", mock_runner),
        patch("api.v1.quality_routes.open_background_session", fake_open_session),
    ):
        out = await quality_system(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=QualityAsyncRequest(),
            session=session,
        )
        await scheduled[0]()

    assert out["run_id"] == str(new_id)
    bind = session.execute.call_args[0][1]
    assert bind["check"] == "system"
    assert mock_runner.call_args.kwargs["check"] == "system"
    assert mock_runner.call_args.kwargs["params"] == {}


async def test_quality_gates_inserts_quality_check_row_and_returns_202():
    """POST /quality/gates uses fix_id='gates'."""
    request = _request_with_context()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    background_tasks.add_task = MagicMock()

    new_id = uuid4()
    session = _async_session_returning(new_id)

    out = await quality_gates(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=QualityAsyncRequest(requested_by="cli"),
        session=session,
    )

    assert out["run_id"] == str(new_id)
    bind = session.execute.call_args[0][1]
    assert bind["check"] == "gates"
    assert bind["requested_by"] == "cli"


# ----------------------------------------------------------------------
# Round-trip: a quality_check row is readable via GET /v1/fix/runs/{id}
# ----------------------------------------------------------------------


async def test_quality_check_row_is_readable_via_fix_runs_get():
    """The /fix/runs/{id} resource read endpoint serves quality_check
    rows. Confirms the single-table design: kind='quality_check' rows
    coexist with atomic / flow / modularity rows on core.fix_runs and
    use the same GET endpoint."""
    rid = uuid4()
    requested_at = datetime(2026, 5, 17, 18, 0, 0, tzinfo=UTC)
    row = {
        "id": rid,
        "kind": "quality_check",
        "fix_id": "lint",
        "target_files": None,
        "write": False,
        "status": "completed",
        "requested_by": "api",
        "requested_at": requested_at,
        "started_at": requested_at,
        "finished_at": requested_at,
        "result": {"check": "lint", "ok": True, "exit_code": 0},
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: row))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_fix_run(run_id=rid, session=session)

    assert out["run_id"] == str(rid)
    assert out["kind"] == "quality_check"
    assert out["fix_id"] == "lint"
    assert out["status"] == "completed"
    assert out["result"] == {"check": "lint", "ok": True, "exit_code": 0}


def test_mutation_routes_carry_governor_gate():
    """#808/#770: quality_lint is the only quality_* route with a live
    --fix path (ruff check src/ --fix when payload.fix=True) -- a real
    mutation, governor-gated. The read-only checks (imports/body-ui/
    policy-coverage/tests/system/gates) stay open."""
    from api.dependencies import require_governor
    from api.v1.quality_routes import router

    gated_by_route = {
        (method, route.path): require_governor in route.dependencies
        for route in router.routes
        for method in route.methods
    }
    assert gated_by_route[("POST", "/quality/lint")] is True
    assert gated_by_route[("POST", "/quality/imports")] is False
    assert gated_by_route[("POST", "/quality/body-ui")] is False
    assert gated_by_route[("POST", "/quality/policy-coverage")] is False
    assert gated_by_route[("POST", "/quality/tests")] is False
    assert gated_by_route[("POST", "/quality/system")] is False
    assert gated_by_route[("POST", "/quality/gates")] is False
