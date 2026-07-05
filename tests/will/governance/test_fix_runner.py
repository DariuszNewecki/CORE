# tests/will/governance/test_fix_runner.py

"""Unit tests for the fix_runner result models (ADR-056 D7, #454).

Covers the FixRunResult / QualityGateResult contracts' governed classes:
construction per kind, the exclude_none serialisation that produces the
core.fix_runs.result JSONB shape, the closed kind vocabulary, and a
persist round-trip confirming run_and_persist_fix emits the atomic shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from will.governance.fix_runner import (
    FixRunResult,
    QualityGateResult,
    run_and_persist_fix,
)


def test_fix_run_result_atomic_payload_drops_inapplicable_fields():
    """kind=atomic carries data + duration_sec; flow/modularity fields omitted."""
    payload = FixRunResult(
        kind="atomic",
        ok=True,
        data={"files_changed": 3},
        duration_sec=4.2,
    ).as_payload()

    assert payload == {
        "kind": "atomic",
        "ok": True,
        "data": {"files_changed": 3},
        "duration_sec": 4.2,
    }
    assert "flow_id" not in payload
    assert "files" not in payload


def test_fix_run_result_flow_payload_includes_steps():
    """kind=flow carries flow_id + steps; modularity fields omitted."""
    payload = FixRunResult(
        kind="flow",
        ok=False,
        flow_id="flow.fix_code",
        duration_sec=1.0,
        steps=[{"ref_id": "s1", "ok": False}],
    ).as_payload()

    assert payload["kind"] == "flow"
    assert payload["flow_id"] == "flow.fix_code"
    assert payload["steps"] == [{"ref_id": "s1", "ok": False}]
    assert "count" not in payload


def test_fix_run_result_modularity_payload():
    """kind=modularity carries the batch counters + per-file results."""
    payload = FixRunResult(
        kind="modularity",
        ok=True,
        count=2,
        successes=2,
        failures=0,
        files=[{"file": "a.py", "success": True}],
    ).as_payload()

    assert payload["kind"] == "modularity"
    assert payload["successes"] == 2
    assert "data" not in payload


def test_fix_run_result_rejects_unknown_kind():
    """The kind discriminator is a closed vocabulary."""
    with pytest.raises(ValidationError):
        FixRunResult(kind="bogus", ok=True)


def test_quality_gate_result_payload_round_trips_components():
    """QualityGateResult preserves the per-gate component map verbatim."""
    components = {
        "ruff": {"ok": True, "exit_code": 0, "is_warning": False},
        "radon": {"ok": False, "exit_code": 1, "is_warning": True},
    }
    payload = QualityGateResult(
        check="gates", ok=True, components=components
    ).as_payload()

    assert payload == {"check": "gates", "ok": True, "components": components}


async def test_run_and_persist_fix_writes_atomic_fix_run_result_shape():
    """run_and_persist_fix persists a kind='atomic' FixRunResult payload."""
    run_id = uuid4()
    session = AsyncMock()

    action_result = MagicMock()
    action_result.ok = True
    action_result.data = {"files_changed": 1}
    action_result.duration_sec = 2.5

    executor = MagicMock()
    executor.execute = AsyncMock(return_value=action_result)

    captured: dict = {}

    async def fake_update(_session, _run_id, status, **kwargs):
        if "result" in kwargs:
            captured["status"] = status
            captured["result"] = kwargs["result"]

    with (
        patch("will.governance.fix_runner.ActionExecutor", return_value=executor),
        patch(
            "will.governance.fix_runner._update_fix_run_status", side_effect=fake_update
        ),
    ):
        await run_and_persist_fix(
            MagicMock(),
            session,
            run_id=run_id,
            fix_id="fix.format",
            target_files=None,
            write=False,
        )

    assert captured["status"] == "completed"
    assert captured["result"] == {
        "kind": "atomic",
        "ok": True,
        "data": {"files_changed": 1},
        "duration_sec": 2.5,
    }
