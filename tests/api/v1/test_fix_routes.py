# tests/api/v1/test_fix_routes.py

"""Unit tests for fix_routes — ADR-055 Phase 2, D2.

Mocks will.governance.fix_runner facades so assertions target the route
translation layer (INSERT shape, 202/422/404 status, background-task
scheduling) — not the underlying execution pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from pydantic import ValidationError

from api.v1.fix_routes import (
    RunFixRequest,
    RunFlowRequest,
    RunIRRequest,
    get_fix_run,
    list_actions,
    list_fix_commands,
    run_fix,
    run_fix_all,
    run_fix_ir,
    run_fix_modularity,
)


def _mock_request():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


def _mock_session_returning(run_id):
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one = MagicMock(return_value=run_id)
    session.execute = AsyncMock(return_value=result_obj)
    session.commit = AsyncMock()
    return session


# ── RunFixRequest validation ──────────────────────────────────────────────────

def test_run_fix_request_rejects_absolute_path():
    """Paths starting with '/' are rejected at model construction time."""
    with pytest.raises(ValidationError):
        RunFixRequest(target_files=["/etc/passwd"])


def test_run_fix_request_rejects_path_traversal():
    """Paths containing '..' are rejected at model construction time."""
    with pytest.raises(ValidationError):
        RunFixRequest(target_files=["../../etc/shadow"])


def test_run_fix_request_accepts_relative_path():
    """Relative paths without traversal are valid."""
    r = RunFixRequest(target_files=["src/body/foo.py"])
    assert r.target_files == ["src/body/foo.py"]


# ── run_fix ───────────────────────────────────────────────────────────────────

async def test_run_fix_unknown_id_raises_422():
    """Unknown fix_id returns 422 with the id name in the detail."""
    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value=["fix.format", "fix.imports"],
    ):
        with pytest.raises(HTTPException) as exc:
            await run_fix(
                fix_id="fix.nonexistent",
                request=_mock_request(),
                response=MagicMock(spec=Response),
                background_tasks=MagicMock(spec=BackgroundTasks),
                payload=RunFixRequest(),
                session=AsyncMock(),
            )
    assert exc.value.status_code == 422
    assert "fix.nonexistent" in exc.value.detail


async def test_run_fix_valid_id_returns_202_with_pending():
    """Valid fix_id inserts a row, schedules background task, returns pending."""
    run_id = uuid4()
    session = _mock_session_returning(run_id)
    bg = MagicMock(spec=BackgroundTasks)
    bg.add_task = MagicMock()

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value=["fix.format"],
    ):
        out = await run_fix(
            fix_id="fix.format",
            request=_mock_request(),
            response=MagicMock(spec=Response),
            background_tasks=bg,
            payload=RunFixRequest(write=False),
            session=session,
        )

    assert out == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/fix/runs/{run_id}",
    }
    bg.add_task.assert_called_once()
    session.commit.assert_awaited_once()


async def test_run_fix_propagates_write_flag_to_insert():
    """The write flag passed in the payload is stored in the INSERT params."""
    run_id = uuid4()
    session = _mock_session_returning(run_id)
    bg = MagicMock(spec=BackgroundTasks)
    bg.add_task = MagicMock()

    with patch(
        "api.v1.fix_routes.list_registered_action_ids",
        return_value=["fix.format"],
    ):
        await run_fix(
            fix_id="fix.format",
            request=_mock_request(),
            response=MagicMock(spec=Response),
            background_tasks=bg,
            payload=RunFixRequest(write=True),
            session=session,
        )

    insert_params = session.execute.await_args.args[1]
    assert insert_params["write"] is True


# ── run_fix_all ───────────────────────────────────────────────────────────────

async def test_run_fix_all_unknown_flow_raises_422():
    """When flow.fix_code is absent from the flow registry, 422 is raised."""
    with patch("api.v1.fix_routes.list_registered_flow_ids", return_value=[]):
        with pytest.raises(HTTPException) as exc:
            await run_fix_all(
                request=_mock_request(),
                response=MagicMock(spec=Response),
                background_tasks=MagicMock(spec=BackgroundTasks),
                payload=RunFlowRequest(),
                session=AsyncMock(),
            )
    assert exc.value.status_code == 422


async def test_run_fix_all_dispatches_flow_and_returns_202():
    """Valid flow.fix_code inserts a row of kind='flow' and returns 202."""
    run_id = uuid4()
    session = _mock_session_returning(run_id)
    bg = MagicMock(spec=BackgroundTasks)
    bg.add_task = MagicMock()

    with patch(
        "api.v1.fix_routes.list_registered_flow_ids",
        return_value=["flow.fix_code"],
    ):
        out = await run_fix_all(
            request=_mock_request(),
            response=MagicMock(spec=Response),
            background_tasks=bg,
            payload=RunFlowRequest(),
            session=session,
        )

    assert out["status"] == "pending"
    assert out["href"] == f"/v1/fix/runs/{run_id}"
    bg.add_task.assert_called_once()


# ── run_fix_modularity ────────────────────────────────────────────────────────

async def test_run_fix_modularity_returns_202():
    """Modularity endpoint inserts a row (no flow_id validation) and returns 202."""
    run_id = uuid4()
    session = _mock_session_returning(run_id)
    bg = MagicMock(spec=BackgroundTasks)
    bg.add_task = MagicMock()

    out = await run_fix_modularity(
        request=_mock_request(),
        response=MagicMock(spec=Response),
        background_tasks=bg,
        payload=RunFlowRequest(),
        session=session,
    )

    assert out == {
        "run_id": str(run_id),
        "status": "pending",
        "href": f"/v1/fix/runs/{run_id}",
    }
    bg.add_task.assert_called_once()


# ── run_fix_ir ────────────────────────────────────────────────────────────────

async def test_run_fix_ir_returns_written_path():
    """POST /fix/ir delegates to bootstrap_ir and returns {path}."""
    with patch(
        "api.v1.fix_routes.bootstrap_ir",
        return_value="var/ir/triage_2026-07-06.yaml",
    ) as mock_ir:
        out = await run_fix_ir(
            request=_mock_request(),
            payload=RunIRRequest(kind="triage"),
        )
    mock_ir.assert_called_once()
    assert out == {"path": "var/ir/triage_2026-07-06.yaml"}


async def test_run_fix_ir_bootstrap_error_becomes_422():
    """ValueError raised by bootstrap_ir is translated to HTTPException(422)."""
    with patch(
        "api.v1.fix_routes.bootstrap_ir",
        side_effect=ValueError("unsupported kind"),
    ):
        with pytest.raises(HTTPException) as exc:
            await run_fix_ir(
                request=_mock_request(),
                payload=RunIRRequest(kind="log"),
            )
    assert exc.value.status_code == 422
    assert "unsupported kind" in exc.value.detail


# ── list_fix_commands ─────────────────────────────────────────────────────────

async def test_list_fix_commands_returns_count_and_filtered_commands():
    """GET /fix/commands delegates to list_action_definitions(category='fix')."""
    commands = [{"action_id": "fix.format", "category": "fix"}]
    with patch(
        "api.v1.fix_routes.list_action_definitions",
        return_value=commands,
    ) as mock_list:
        out = await list_fix_commands()
    mock_list.assert_called_once_with(category="fix")
    assert out == {"count": 1, "commands": commands}


async def test_list_fix_commands_empty_registry():
    """Empty registry returns count=0 and empty list — not an error."""
    with patch("api.v1.fix_routes.list_action_definitions", return_value=[]):
        out = await list_fix_commands()
    assert out == {"count": 0, "commands": []}


# ── list_actions ──────────────────────────────────────────────────────────────

async def test_list_actions_returns_all_unfiltered():
    """GET /actions returns every registered action with no category filter."""
    all_actions = [
        {"action_id": "fix.format"},
        {"action_id": "build.tests"},
    ]
    with patch(
        "api.v1.fix_routes.list_action_definitions",
        return_value=all_actions,
    ) as mock_list:
        out = await list_actions()
    mock_list.assert_called_once_with()
    assert out == {"count": 2, "actions": all_actions}


# ── get_fix_run ───────────────────────────────────────────────────────────────

async def test_get_fix_run_returns_row_with_iso_timestamps():
    """GET /fix/runs/{id} returns the persisted row; datetimes are ISO strings."""
    run_id = uuid4()
    ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    row = {
        "id": run_id,
        "kind": "atomic",
        "fix_id": "fix.format",
        "target_files": None,
        "write": False,
        "status": "completed",
        "requested_by": "api",
        "requested_at": ts,
        "started_at": ts,
        "finished_at": ts,
        "result": {"ok": True},
        "error": None,
    }
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_fix_run(run_id=run_id, session=session)

    assert out["run_id"] == str(run_id)
    assert out["kind"] == "atomic"
    assert out["fix_id"] == "fix.format"
    assert out["status"] == "completed"
    assert out["started_at"] == ts.isoformat()
    assert out["error"] is None


async def test_get_fix_run_null_timestamps_are_none():
    """Pending rows have null timestamps; route must return None, not crash."""
    run_id = uuid4()
    row = {
        "id": run_id,
        "kind": "flow",
        "fix_id": "flow.fix_code",
        "target_files": None,
        "write": False,
        "status": "pending",
        "requested_by": "api",
        "requested_at": None,
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result_obj)

    out = await get_fix_run(run_id=run_id, session=session)

    assert out["status"] == "pending"
    assert out["started_at"] is None
    assert out["finished_at"] is None


async def test_get_fix_run_raises_404_for_unknown_id():
    """Unknown run_id raises HTTPException(404)."""
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.mappings.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)

    with pytest.raises(HTTPException) as exc:
        await get_fix_run(run_id=uuid4(), session=session)

    assert exc.value.status_code == 404
