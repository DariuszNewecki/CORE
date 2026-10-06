# tests/will/workers/audit_violation_sensor/test_drain.py
"""Clean-pass drains extracted from AuditViolationSensor.run (ADR-045, ADR-127)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from will.audit_violation.drain import drain_cleared_findings


def _bb(released=(), resolved=(), indet=(), aband=()) -> SimpleNamespace:
    return SimpleNamespace(
        adjudicate_awaiting_reaudit_findings=AsyncMock(
            return_value={
                "released_subjects": list(released),
                "resolved_subjects": list(resolved),
            }
        ),
        adjudicate_indeterminate_findings=AsyncMock(
            return_value={"resolved_subjects": list(indet)}
        ),
        adjudicate_abandoned_findings=AsyncMock(
            return_value={"resolved_subjects": list(aband)}
        ),
    )


@pytest.mark.asyncio
async def test_no_movement_returns_none_and_scopes_every_drain() -> None:
    bb = _bb()
    result = await drain_cleared_findings(
        bb,
        artifact_type_id="python",
        rule_namespace="purity",
        current_violations=[
            {"rule_id": "purity.x", "file_path": "src/a.py"},
            {"file_path": "src/b.py"},
        ],
    )
    assert result is None
    expected_subjects = {"python::purity.x::src/a.py", "python::purity::src/b.py"}
    for method in (
        bb.adjudicate_awaiting_reaudit_findings,
        bb.adjudicate_indeterminate_findings,
        bb.adjudicate_abandoned_findings,
    ):
        kwargs = method.await_args.kwargs
        assert kwargs["subject_prefix"] == "python::purity"
        assert kwargs["current_violation_subjects"] == expected_subjects
        assert kwargs["resolved_by"] == "audit_violation_sensor"


@pytest.mark.asyncio
async def test_movement_returns_report_payload() -> None:
    bb = _bb(released=["r1"], resolved=["s1", "s2"], indet=["i1"], aband=["a1"])
    result = await drain_cleared_findings(
        bb, artifact_type_id="python", rule_namespace="purity", current_violations=[]
    )
    assert result == {
        "rule_namespace": "purity",
        "released_count": 1,
        "resolved_count": 2,
        "released_subjects": ["r1"],
        "resolved_subjects": ["s1", "s2"],
        "indeterminate_drained": 1,
        "indeterminate_drain_subjects": ["i1"],
        "abandoned_drained": 1,
        "abandoned_drain_subjects": ["a1"],
    }
