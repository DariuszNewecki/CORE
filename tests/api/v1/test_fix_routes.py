# tests/api/v1/test_fix_routes.py

"""Unit tests for fix_routes — ADR-055 Phase 2.

Mocks `list_registered_action_ids` / `run_and_persist_fix` so the
assertions target the route translation layer, not the underlying
ActionExecutor pipeline. Sessions are mocked AsyncSession instances.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.v1.fix_routes import (
    FIX_CODE_FLOW_ID,
    RunFixRequest,
    RunFlowRequest,
    RunIRRequest,
    get_fix_run,
    list_actions,
    list_fix_commands,
    router,
    run_fix,
    run_fix_all,
    run_fix_ir,
    run_fix_modularity,
)


async def test_run_fix_known_id_inserts_pending_and_schedules_background():
    """Known fix_id inserts a pending row, schedules background task,
    and returns 202 with run_id, status, and href."""
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

    payload = RunFixRequest(target_files=["src/foo.py"], write=False)

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value={"fix.format", "fix.imports"},
    ):
        out = await run_fix(
            fix_id="fix.format",
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert out == {
        "run_id": str(new_id),
        "status": "pending",
        "href": f"/v1/fix/runs/{new_id}",
    }
    assert response.status_code == 202
    assert background_tasks.add_task.call_count == 1
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_run_fix_unknown_id_returns_422_without_inserting():
    """Unknown fix_id raises HTTPException(422) and never touches the DB."""
    request = MagicMock()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()

    payload = RunFixRequest()

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value={"fix.format"},
    ):
        with pytest.raises(HTTPException) as exc_info:
            await run_fix(
                fix_id="not.a.real.action",
                request=request,
                response=response,
                background_tasks=background_tasks,
                payload=payload,
                session=session,
            )

    assert exc_info.value.status_code == 422
    assert "not.a.real.action" in exc_info.value.detail["error"]
    session.execute.assert_not_awaited()
    background_tasks.add_task.assert_not_called()


@pytest.mark.parametrize("fix_id", ["fix.imports", "fix.headers", "sync.db"])
async def test_run_fix_dispatches_distinct_known_action_ids(fix_id):
    """The route forwards whatever fix_id passed validation — no
    hard-coded values, no special-casing per action. Exercises three
    distinct registered ids to satisfy ADR-055 #349 acceptance."""
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

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value={"fix.imports", "fix.headers", "sync.db"},
    ):
        out = await run_fix(
            fix_id=fix_id,
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=RunFixRequest(),
            session=session,
        )

    assert out["run_id"] == str(new_id)
    assert response.status_code == 202
    bind = session.execute.call_args[0][1]
    assert bind["fix_id"] == fix_id


async def test_run_fix_passes_target_files_as_json_and_write_flag():
    """The INSERT serialises target_files as JSON and forwards `write`
    and `requested_by` verbatim to the SQL bind params."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    new_id = uuid4()
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    payload = RunFixRequest(
        target_files=["a.py", "b.py"],
        write=True,
        requested_by="cli",
    )

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value={"fix.format"},
    ):
        await run_fix(
            fix_id="fix.format",
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    bind = session.execute.call_args[0][1]
    assert bind["fix_id"] == "fix.format"
    assert bind["write"] is True
    assert bind["requested_by"] == "cli"
    # JSON-encoded list, not the raw Python list.
    assert bind["target_files"] == '["a.py", "b.py"]'


async def test_run_fix_null_target_files_persisted_as_null():
    """target_files=None must be persisted as SQL NULL, not 'null' string."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=uuid4())
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value={"fix.format"},
    ):
        await run_fix(
            fix_id="fix.format",
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=RunFixRequest(target_files=None),
            session=session,
        )

    bind = session.execute.call_args[0][1]
    assert bind["target_files"] is None


async def test_get_fix_run_returns_full_record():
    """GET returns the persisted row with id renamed to run_id and
    timestamps ISO-formatted."""
    rid = uuid4()
    requested_at = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    started_at = datetime(2026, 5, 17, 12, 0, 1, tzinfo=UTC)
    finished_at = datetime(2026, 5, 17, 12, 0, 5, tzinfo=UTC)
    result_payload = {"ok": True, "data": {"files_changed": 3}, "duration_sec": 4.2}

    row = {
        "id": rid,
        "kind": "atomic",
        "fix_id": "fix.format",
        "target_files": ["a.py"],
        "write": True,
        "status": "completed",
        "requested_by": "api",
        "requested_at": requested_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": result_payload,
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: row))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_fix_run(run_id=rid, session=session)

    assert out["run_id"] == str(rid)
    assert out["kind"] == "atomic"
    assert out["fix_id"] == "fix.format"
    assert out["target_files"] == ["a.py"]
    assert out["write"] is True
    assert out["status"] == "completed"
    assert out["requested_by"] == "api"
    assert out["requested_at"] == requested_at.isoformat()
    assert out["started_at"] == started_at.isoformat()
    assert out["finished_at"] == finished_at.isoformat()
    assert out["result"] == result_payload
    assert out["error"] is None


async def test_get_fix_run_pending_row_has_null_lifecycle_timestamps():
    """A pending row has started_at / finished_at / result = None — the
    route must preserve those as nulls, not coerce to placeholders."""
    rid = uuid4()
    row = {
        "id": rid,
        "kind": "atomic",
        "fix_id": "fix.format",
        "target_files": None,
        "write": False,
        "status": "pending",
        "requested_by": "api",
        "requested_at": datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: row))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_fix_run(run_id=rid, session=session)

    assert out["status"] == "pending"
    assert out["started_at"] is None
    assert out["finished_at"] is None
    assert out["result"] is None


async def test_get_fix_run_unknown_id_raises_404():
    """Unknown run_id raises HTTPException(404)."""
    rid = uuid4()
    result_obj = MagicMock()
    result_obj.mappings = MagicMock(return_value=MagicMock(first=lambda: None))

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_obj)

    with pytest.raises(HTTPException) as exc_info:
        await get_fix_run(run_id=rid, session=session)

    assert exc_info.value.status_code == 404
    assert str(rid) in exc_info.value.detail


# ----------------------------------------------------------------------
# GET /fix/commands and GET /actions
# ----------------------------------------------------------------------


async def test_list_fix_commands_returns_filtered_actions():
    """GET /fix/commands wraps list_action_definitions(category='fix')."""
    sample = [
        {
            "action_id": "fix.format",
            "description": "format",
            "category": "fix",
            "policies": [],
            "impact_level": "safe",
            "requires_db": False,
            "requires_vectors": False,
            "remediates": [],
        }
    ]

    with patch(
        "api.v1.fix_routes.list_action_definitions",
        return_value=sample,
    ) as mock:
        out = await list_fix_commands()

    mock.assert_called_once_with(category="fix")
    assert out == {"count": 1, "commands": sample}


async def test_list_actions_returns_unfiltered_action_list():
    """GET /actions wraps list_action_definitions() with no category filter."""
    sample = [
        {
            "action_id": "fix.format",
            "description": "format",
            "category": "fix",
            "policies": [],
            "impact_level": "safe",
            "requires_db": False,
            "requires_vectors": False,
            "remediates": [],
        },
        {
            "action_id": "sync.db",
            "description": "sync db",
            "category": "sync",
            "policies": [],
            "impact_level": "moderate",
            "requires_db": True,
            "requires_vectors": False,
            "remediates": [],
        },
    ]

    with patch(
        "api.v1.fix_routes.list_action_definitions",
        return_value=sample,
    ) as mock:
        out = await list_actions()

    mock.assert_called_once_with()
    assert out == {"count": 2, "actions": sample}


# ----------------------------------------------------------------------
# POST /fix/all
# ----------------------------------------------------------------------


async def test_run_fix_all_known_flow_inserts_pending_and_schedules():
    """Known fix_code flow inserts a pending row, schedules background
    task, returns 202 with run_id and href; kind column = 'flow'."""
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

    payload = RunFlowRequest(write=False)

    with patch(
        "api.v1.fix_routes.list_registered_flow_ids",
        return_value={FIX_CODE_FLOW_ID, "flow.dev_sync"},
    ):
        out = await run_fix_all(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert out["run_id"] == str(new_id)
    assert out["status"] == "pending"
    assert out["href"] == f"/v1/fix/runs/{new_id}"
    assert response.status_code == 202
    assert background_tasks.add_task.call_count == 1
    bind = session.execute.call_args[0][1]
    assert bind["kind"] == "flow"
    assert bind["flow_id"] == FIX_CODE_FLOW_ID
    assert bind["write"] is False


async def test_run_fix_all_unknown_flow_returns_422():
    """If flow.fix_code is not registered, the route 422s before INSERT."""
    request = MagicMock()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    session = AsyncMock()

    with patch(
        "api.v1.fix_routes.list_registered_flow_ids",
        return_value={"flow.something_else"},
    ):
        with pytest.raises(HTTPException) as exc_info:
            await run_fix_all(
                request=request,
                response=response,
                background_tasks=background_tasks,
                payload=RunFlowRequest(),
                session=session,
            )

    assert exc_info.value.status_code == 422
    assert FIX_CODE_FLOW_ID in exc_info.value.detail["error"]
    session.execute.assert_not_awaited()
    background_tasks.add_task.assert_not_called()


# ----------------------------------------------------------------------
# POST /fix/modularity
# ----------------------------------------------------------------------


async def test_run_fix_modularity_inserts_pending_and_schedules():
    """A valid body always returns 202: the modularity route is backed
    by a Python-level workflow, not a Flow YAML, so there is no flow
    registry to validate against. The INSERT sets kind='modularity' and
    fix_id=NULL."""
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

    out = await run_fix_modularity(
        request=request,
        response=response,
        background_tasks=background_tasks,
        payload=RunFlowRequest(write=True),
        session=session,
    )

    assert out["run_id"] == str(new_id)
    assert out["status"] == "pending"
    assert out["href"] == f"/v1/fix/runs/{new_id}"
    assert response.status_code == 202
    assert background_tasks.add_task.call_count == 1
    # No flow_id bind param — fix_id is hard-coded to NULL in the SQL.
    bind = session.execute.call_args[0][1]
    assert "flow_id" not in bind
    assert bind["write"] is True


async def test_run_fix_modularity_background_task_reaches_runner():
    """The scheduled background task delegates to run_and_persist_modularity
    with the correct run_id and write flag."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    response = MagicMock(spec=Response)
    background_tasks = MagicMock(spec=BackgroundTasks)
    scheduled: list = []
    background_tasks.add_task = MagicMock(side_effect=lambda fn: scheduled.append(fn))

    new_id = uuid4()
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=new_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()

    async def fake_open_session():
        yield AsyncMock()

    mock_runner = AsyncMock()
    with (
        patch("api.v1.fix_routes.run_and_persist_modularity", mock_runner),
        patch("api.v1.fix_routes.open_background_session", fake_open_session),
    ):
        await run_fix_modularity(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=RunFlowRequest(write=False),
            session=session,
        )
        assert len(scheduled) == 1
        await scheduled[0]()

    mock_runner.assert_awaited_once()
    kwargs = mock_runner.call_args.kwargs
    assert kwargs["run_id"] == new_id
    assert kwargs["write"] is False


# ----------------------------------------------------------------------
# POST /fix/ir
# ----------------------------------------------------------------------


async def test_run_fix_ir_triage_returns_path():
    """Triage kind delegates to bootstrap_ir and returns the written path."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()

    with patch(
        "api.v1.fix_routes.bootstrap_ir",
        return_value=".intent/mind/ir/triage_log.yaml",
    ) as mock:
        out = await run_fix_ir(
            request=request,
            payload=RunIRRequest(kind="triage"),
        )

    mock.assert_called_once_with(request.app.state.core_context, "triage")
    assert out == {"path": ".intent/mind/ir/triage_log.yaml"}


async def test_run_fix_ir_log_returns_path():
    """Log kind delegates to bootstrap_ir and returns the written path."""
    request = MagicMock()
    request.app.state.core_context = MagicMock()

    with patch(
        "api.v1.fix_routes.bootstrap_ir",
        return_value=".intent/mind/ir/incident_log.yaml",
    ) as mock:
        out = await run_fix_ir(
            request=request,
            payload=RunIRRequest(kind="log"),
        )

    mock.assert_called_once_with(request.app.state.core_context, "log")
    assert out == {"path": ".intent/mind/ir/incident_log.yaml"}


# ---------------------------------------------------------------------------
# RBAC route-level tests — #707 / #710
# ---------------------------------------------------------------------------


def _make_fix_client(role: str) -> TestClient:
    """Build a minimal FastAPI test client with the fix router and a mocked
    get_current_user that returns the given role."""
    app = FastAPI()
    app.include_router(router)

    async def _mock_user() -> dict:
        return {"sub": "u1", "email": "u@test.com", "role": role}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


def test_run_fix_ir_non_admin_receives_403() -> None:
    """POST /ir requires platform_admin — visitor gets 403 (#707)."""
    client = _make_fix_client(role="visitor")
    r = client.post("/ir", json={"kind": "triage"})
    assert r.status_code == 403


def test_get_fix_run_non_admin_receives_403() -> None:
    """GET /runs/{run_id} requires platform_admin — visitor gets 403 (#710)."""
    client = _make_fix_client(role="visitor")
    r = client.get(f"/runs/{uuid4()}")
    assert r.status_code == 403
